import subprocess
import argparse
import os
import glob
from concurrent.futures import ThreadPoolExecutor


def list_projects(folder_id, output_file):
    '''list projects in the main folder given and each subsequent folder'''
    print(f"[+] Listing projects in folder {folder_id}")
    with open(output_file, "a") as f:
        result = subprocess.run(
            ["gcloud", "projects", "list",
             f"--filter=parent.id={folder_id} AND parent.type=folder",
             "--format=value(projectId)"], stdout=f, stderr=subprocess.PIPE, text=True
        )
        if result.returncode != 0:
            print(f"Error listing projects: {result.stderr}")
            exit(1)


def explore_folders(parent_id):
    '''recursively explore folders under main folder given'''
    # create output file and clear it
    output_file = "ids.txt"
    with open(output_file, "w") as f:
        pass

    list_projects(parent_id, output_file)
    result = subprocess.run(
        ["gcloud", "resource-manager", "folders", "list",
         f"--folder={parent_id}", "--format=value(name)"], capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"[+] Error listing folders: {result.stderr}")
        exit(1)
        
    folders = result.stdout.strip().split('\n')
    for folder in folders:
        if folder:
            explore_folders(folder.split('/')[-1])

    return output_file


def runscout(id_file):
    '''run scoutsuite command for each project id found'''

    # Check if ids.txt exists
    id_file = "ids.txt"
    if not os.path.isfile(id_file):
        print("[+] Error: File 'ids.txt' not found!\n")
        exit(1)

    # Create the main output directory
    main_directory = "scout_output"
    try:
        os.makedirs(main_directory, exist_ok=True)
    except OSError as e:
        print(f"[+] Failed to create main output directory: {e}\n")
        exit(1)

    # Read each project ID from ids.txt and process it
    with open(id_file, 'r') as file:
        for line in file:
            project_id = line.strip()
            if not project_id:
                continue

            # Create a new directory for the project within the main output directory
            directory = os.path.join(main_directory, f"scout-{project_id}")
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as e:
                print(f"[+] Failed to create directory for project ID {project_id}: {e}\n")
                continue

            # Change to the new directory
            os.chdir(directory)

            # Run the ScoutSuite command
            print(f"[+] Running ScoutSuite for project ID {project_id}...")
            result = subprocess.run(
                ["scout", "gcp", "--user-account", "--project-id", project_id],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                print(f"[+] ScoutSuite command failed for project ID {project_id}: {result.stderr}")
            else:
                print(f"[+] ScoutSuite has completed for project ID {project_id}\n")

            # Change back to the original directory
            os.chdir('..')


def gather_results():
    '''find all scoutsuite_results_gcp*.js files and add the findings into one .js file'''
    # Find all files matching the pattern
    files = glob.glob(f'{os.getcwd()}/scoutsuite_results_*.js')

    # clear file
    with open(f'{os.getcwd()}/all.js', "w") as f:
        pass

    # Open the output file in append mode
    with open(f'{os.getcwd()}/all.js', 'w') as outfile:
        search_pattern = os.path.join(f'{os.getcwd()}/scout_output', '**', 'scoutsuite_results_*.js')
        for filepath in glob.iglob(search_pattern, recursive=True):
            with open(filepath, 'r') as infile:
                # outfile.write(infile.read())
                for line in infile:
                    stripped_line = line.strip()
                    if stripped_line and not stripped_line.startswith('scoutsuite_results ='):
                        outfile.write(line)


def process_service(service, all_js_path):
    '''use jq to pull required info'''
    findings = subprocess.check_output(
        ['jq', '-r',
        f'. as $root | .service_list[] as ${service} | .services[${service}].findings | to_entries[] | select(.value.flagged_items > 0) | "\\(${service})-- \\(.value.description):\\nProject_ID = \\($root.account_id)\\n"',
      all_js_path], text=True)
    return findings


def process_services():
    '''add all checked_items to findings file in no particular order'''
    all_js_path = f'{os.getcwd()}/all.js'
    output_file = f'{os.getcwd()}/findings.txt'

    # Get the list of services
    services = subprocess.check_output(['jq', '-r', '.service_list[]', all_js_path], text=True).splitlines()

    # Use ThreadPoolExecutor to process services concurrently
    with open(output_file, 'w') as f:
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = executor.map(lambda service: process_service(service, all_js_path), services)
            for result in results:
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
    parser.add_argument('-f','--folder_id', help='Folder ID to extract project IDs from', required=True)

    args = parser.parse_args()

    try:
        # run explore_folders func to collect project IDs
        parent_id = args.folder_id
        # output file for ids
        id_file = explore_folders(parent_id)
        print(f"[+] All project IDs have been saved to {id_file}")
        # run scoutsuite
        runscout(id_file)
        # gather results
        print("[+] Gathered all results to all.js...")
        gather_results()
        print('[+] Processing results...')
        process_services()
        print('[+] Grouping findings...')
        group_findings()
        print('[+] Done. Thanks.')
    except Exception as e:
        print(f"[+] An unexpected error occurred. Details: {e}")

if __name__ == '__main__':
    main()
    


