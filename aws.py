
import subprocess
import argparse
import os
import glob
from concurrent.futures import ThreadPoolExecutor

def gather_results(directory):
    search_pattern = os.path.join(f'{directory}', '**', 'scoutsuite_results_*.js')
    all_js_path = f'{directory}/all.js'

    # Open the output file in write mode (this clears the file first)
    with open(all_js_path, 'w') as outfile:
        for filepath in glob.iglob(search_pattern, recursive=True):
            with open(filepath, 'r') as infile:
                for line in infile:
                    stripped_line = line.strip()
                    if stripped_line and not stripped_line.startswith('scoutsuite_results ='):
                        outfile.write(line + '\n')


def process_service(service, all_js_path):
    findings = subprocess.check_output(
    	['jq', '-r',
    	f'. as $root | .service_list[] as ${service} | .services[${service}].findings | to_entries[] | select(.value.flagged_items > 0) | "\\(${service})-- \\(.value.description):\\nAccount_ID = \\($root.account_id)\\n"',
   	  all_js_path], text=True)
    return findings


def process_services(directory):
    all_js_path = f'{directory}/all.js'
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

            elif line.startswith("Account_ID ="):
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
    parser.add_argument('-d', '--directory', help='Path to directory with Scoutsuite results.', required=True)

    args = parser.parse_args()

    try:
        print('[+] Gathering results...')
        gather_results(args.directory)
        print('[+] Processing results...')
        process_services(args.directory)
        print('[+] Grouping findings...')
        group_findings()
        print('[+] Done. Thanks.')
    except Exception as e:
        print(f"An unexpected error occurred. Details: {e}")

if __name__ == '__main__':
    main()