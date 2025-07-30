import subprocess
import argparse
import os
import glob
from concurrent.futures import ThreadPoolExecutor


def list_projects(folder_id, output_file, key_file=None):
    '''list projects in the main folder given and each subsequent folder'''
    print(f"[+] Listing projects in folder {folder_id}")
    cmd = [
        "gcloud", "projects", "list",
        f"--filter=parent.id={folder_id} AND parent.type=folder",
        "--format=value(projectId)"
    ]
    if key_file:
        cmd += ["--key-file", key_file]
    with open(output_file, "a") as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            print(f"Error listing projects: {result.stderr}")
            exit(1)


def explore_folders(parent_id, key_file=None):
    '''recursively explore folders under main folder given'''
    # create output file and clear it
    output_file = "ids.txt"
    open(output_file, "w").close()

    list_projects(parent_id, output_file, key_file)
    cmd = [
        "gcloud", "resource-manager", "folders", "list",
        f"--folder={parent_id}", "--format=value(name)"
    ]
    if key_file:
        cmd += ["--key-file", key_file]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[+] Error listing folders: {result.stderr}")
        exit(1)

    folders = result.stdout.strip().split('\n')
    for folder in folders:
        if folder:
            explore_folders(folder.split('/')[-1], key_file)

    return output_file


def runscout(id_file, key_file=None, user_adc=False):
    '''run scoutsuite command for each project id found'''
    # Check if ids.txt exists
    if not os.path.isfile(id_file):
        print("[+] Error: File 'ids.txt' not found!")
        exit(1)

    # Create the main output directory
    main_directory = "scout_output"
    os.makedirs(main_directory, exist_ok=True)

    # Read each project ID from ids.txt and process it
    with open(id_file, 'r') as file:
        for line in file:
            project_id = line.strip()
            if not project_id:
                continue

            # Create a new directory for the project within the main output directory
            try:
                os.makedirs(main_directory, exist_ok=True)
            except OSError as e:
                print(f"[+] Failed to create directory for project ID {project_id}: {e}\n")
                continue

            # Change to the new directory
            os.chdir(main_directory)

            # Run the ScoutSuite command
            print(f"[+] Running ScoutSuite for project ID {project_id}...")
            cmd = ["scout", "gcp"]
            if key_file:
                cmd += ["--service-account", key_file]
            else:
                cmd += ["--user-account"]
            cmd += ["--project-id", project_id]
            print(f"DEBUG : {cmd}")

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"[+] ScoutSuite failed for {project_id}: {result.stderr}")
            else:
                print(f"[+] ScoutSuite completed for {project_id}")

            # Change back to the original directory
            os.chdir(os.path.join(".."))

  
def gather_results():
    '''find all scoutsuite_results_gcp*.js files and add the findings into one .js file'''
    # Find all files matching the pattern
    files = glob.glob(f'{os.getcwd()}/scoutsuite_results_*.js')
    open(f'{os.getcwd()}/all.js', "w").close()

    # Open the output file in append mode
    with open(f'{os.getcwd()}/all.js', 'w') as outfile:
        search_pattern = os.path.join(f'{os.getcwd()}/scout_output', '**', 'scoutsuite_results_*.js')
        for filepath in glob.iglob(search_pattern, recursive=True):
            with open(filepath, 'r') as infile:
                for line in infile:
                    stripped = line.strip()
                    if stripped and not stripped.startswith('scoutsuite_results ='):
                        outfile.write(line)


def process_service(service, all_js_path):
    '''use jq to pull required info'''
    return subprocess.check_output(
        ['jq', '-r',
        f'. as $root | .service_list[] as ${service} | .services[${service}].findings | to_entries[] | select(.value.flagged_items > 0) | "\\(${service})-- \\(.value.description):\\nProject_ID = \\($root.account_id)\\n"',
      all_js_path], text=True)


def process_services():
    '''add all checked_items to findings file in no particular order'''
    all_js_path = f'{os.getcwd()}/all.js'
    output_file = f'{os.getcwd()}/findings.txt'

    # Get the list of services
    services = subprocess.check_output(['jq', '-r', '.service_list[]', all_js_path], text=True).splitlines()

    # Use ThreadPoolExecutor to process services concurrently
    with open(output_file, 'w') as f:
        with ThreadPoolExecutor(max_workers=4) as executor:
            for result in executor.map(lambda svc: process_service(svc, all_js_path), services):
                f.write(result)


def group_findings():
    '''sort findings into groups based on service names and finding descriptions'''
    findings_file = f'{os.getcwd()}/findings.txt'
    output_file = f'{os.getcwd()}/grouped_findings.txt'
    findings_dict = {}

    with open(findings_file, "r") as file:
        lines = file.readlines()
        current_service = None
        current_description = None

        for line in lines:
            line = line.strip()
            if "--" in line:
                service, description = line.split("--", 1)
                service = service.strip()
                description = description.strip()

                if service not in findings_dict:
                    findings_dict[service] = {}

                if description not in findings_dict[service]:
                    findings_dict[service][description] = []

                current_service = service
                current_description = description

            elif line.startswith("Project_ID ="):
                if current_service and current_description:
                    findings_dict[current_service][current_description].append(line)

    with open(output_file, "w") as file:
        for service, descriptions in findings_dict.items():
            file.write(f"{service.upper()}:\n")
            for description, account_ids in descriptions.items():
                file.write(f"    {description}\n")
                for account_id in set(account_ids):  # Use set to remove duplicates
                    file.write(f"        {account_id}\n")
            file.write("\n")


def main():
    parser = argparse.ArgumentParser()
    g1 = parser.add_mutually_exclusive_group(required=True)
    g1.add_argument('-f', '--folder_id', help='Folder ID to extract project IDs from')
    g1.add_argument('-p', '--projects', help='File with project IDs')

    g2 = parser.add_mutually_exclusive_group(required=True)
    g2.add_argument('--service-account', help='Full path to service account key file')
    g2.add_argument('--user-account', action='store_true', help='Use application default credentials')

    args = parser.parse_args()

    if args.projects:
        id_file = args.projects
    else:
        id_file = explore_folders(args.folder_id, args.service_account)
        print(f"[+] All project IDs have been saved to {id_file}")

    runscout(id_file, key_file=args.service_account, user_adc=args.user_account)
    print("[+] Gathered all results to all.js")
    gather_results()
    print("[+] Processing results")
    process_services()
    print("[+] Grouping findings")
    group_findings()
    print("[+] Done")

if __name__ == '__main__':
    main()
