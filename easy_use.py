from dsp_cli.DSP_submission import DspCLI
from importer.create_json_from_spreadsheet import get_json_from_map
from importer.create_json_from_spreadsheet import write_json_to_submit
from ingest.importer.importer import XlsImporter
from ingest.api.ingestapi import IngestApi
import inspect
import json as js


def show_cli_options(dsp):
    method_list = [func for func in dir(dsp) if callable(getattr(dsp, func)) and not func.startswith("_")]
    join_chars = '\n\t'
    print(f"Please select one of the options:\n\t{join_chars.join([f'{i + 1} - {method_list[i]}' for i in range(len(method_list))])}")
    print(f"\t{len(method_list) + 1} - Exit")
    while True:
        try:
            option = int(input())
            if 0 < option <= len(method_list) + 1:
                break
            else:
                print("Please provide with a proper number")
        except ValueError:
            print("Please provide with a proper number")
    if option == len(method_list) + 1:
        return False
    else:
        return method_list[option - 1]

def call_function(function, dsp):
    called_function = getattr(dsp, function)
    arguments = []
    parameters = inspect.getfullargspec(called_function)
    # Submit_submittable has to have its own code in order to allow indicating for files or json string
    if function == "submit_submittable":
        decision = input("Would you like to retrieve the submittable json from a file? [Y/n]").lower()
        # User provides with path to a file
        if decision not in ["no", "n"]:
            submittable_file = input("Please provide the relative or full path to the file: ")
            with open(submittable_file, "r") as f:
                submittable_json = js.loads(f.read())
        # User provides with string to convert to json object
        else:
            submittable_json = js.loads(input("Please provide with JSON string:\n"))
        submittable_type = input("Please provide with submittable type: if not sure, leave blank and you'll "
                                      "be asked later")
        called_function(submittable_type, submittable_json)

    elif len(parameters.args) > 1:
        for parameter in parameters.args[1:]:
            arguments.append(input(f"Please input value for argument {parameter}: "))
        called_function(*arguments)
    else:
        called_function()
    input("Press <enter> to continue.")

def main():
    dsp = DspCLI()
    print("Welcome to the HCA to DSP easy use script! Please, select the option that better suits your needs:\n")
    print("1 - Submission for dummies: Guided submisssion through the DSP, with indications and questions along the way\n"
          "2 - I want to do my own thing: Access to all the functions the DspCLI object provides\n"
          "3 - I just want to convert a spreadsheet into submittable objects and then exit.")
    while True:
        try:
            option = int(input())
            if 0 < option < 4:
                break
            else:
                print("Please select a valid option: 1, 2 or 3\n")
        except ValueError:
            print("Please select a valid option: 1, 2 or 3\n")

    if option == 2:
        while True:
            cli_function = show_cli_options(dsp)
            if not cli_function:
                break
            call_function(cli_function, dsp)
    if option == 3:
        # Import the spreadsheet with HCA ingest importer
        input_path = input("Please provide with the path to the HCA spreadsheet file: ")
        print("Importing; Might take some time to process...\n\n")
        api = IngestApi(url="https://api.ingest.data.humancellatlas.org/")
        importer = XlsImporter(api)
        spreadsheet = importer.dry_run_import_file(input_path)
        entity_map = spreadsheet.get_entities()

        # Get JSON object list from the entity map
        json_list = get_json_from_map(entity_map)

        # Write to folder
        output_path = input("Please provide with the folder path for the submittable outputs: ")
        write_json_to_submit(json_list, output_path)
        print(f"Saved submittable JSONs to folder {output_path}")
    print("Goodbye! :)")

if __name__ == '__main__':
    main()