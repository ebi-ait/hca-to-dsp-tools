import requests as rq
from pprint import pprint
import os
import json as js


# TODO Create delete_submission()

class DspCLI():
    def __init__(self):
        self.user, self.password,self.root = self._retrieve_credentials()
        self.token = self._retrieve_token()
        self.team_url = f"{self.root}user/teams/"
        self.headers = {'Content-Type': 'application/json;charset=UTF-8', 'Accept': 'application/hal+json',
                        'Authorization': f'Bearer {self.token}'}
        self.accepted_submission_types = {"project": "projects",
                                          "samples": "samples",
                                          "enaStudies": "enaStudies",
                                          "Assay": "studies"}
        self.submission = ''
        self.team = ''
        self.current_link = ''
        self.submission_content = ''
        self.submission_status = ''
        self.current_project = ''
        self.current_project_status = ''
        self.samples = ''
        self.studies = ''
        self.validation_results = ''
        self.processing_status = ''

    # TODO create pretty version of list_submissions (show_submissions?)
    def list_submissions(self):
        pprint(rq.get(f'{self.root}user/submissions', headers=self.headers).json())

    def _retrieve_token(self):
        dev = 'explore.' if '-test' in self.root else ''
        return rq.get(f"https://{dev}api.aai.ebi.ac.uk/auth", auth=(self.user, self.password)).text.strip()

    def _update_token(self):
        self.token = self._retrieve_token()
        self.headers = {'Content-Type': 'application/json;charset=UTF-8', 'Accept': 'application/hal+json',
                        'Authorization': f'Bearer {self.token}'}
        self._retrieve_submission_content()

    def _retrieve_credentials(self):
        with open('cred.txt', 'r') as f:
            user = f.readline().split('=')[-1].strip()
            password = f.readline().split('=')[-1].strip()
            root = f.readline().split('=')[-1].strip()
        return user, password,root

    def create_new_team(self, description, centreName):
        post = {'description': description, 'centreName': centreName}
        response = rq.post(self.team_url, json=post, headers=self.headers)
        # Every time a new team is created we need to update the token and therefore the headers
        self.token = self._retrieve_token()
        self.headers = {'Content-Type': 'application/json', 'Accept': 'application/hal+json',
                        'Authorization': f'Bearer {self.token}'}
        return response.json()

    def create_empty_submission(self, name=''):
        if not self.team:
            self.select_team()
        json = {} if not name else {'name': name}
        url = self.team['_links']['submissions:create']['href']
        self.submission = rq.post(url=url, json=json, headers=self.headers).json()
        self._update_token()

    def select_team(self):
        teams = rq.get(self.team_url, headers=self.headers).json()
        print("The teams are the following:")
        n = 1
        for team in teams['_embedded']['teams']:
            print(f"{n} - {team['name']}")
            n += 1
        team_index = int(input("Please select a number: ")) - 1
        self.team = teams['_embedded']['teams'][team_index]

    def select_submission(self):
        if not self.team:
            self.select_team()
        print("The submissions are the following:")
        submissions = rq.get(self.team['_links']['submissions']['href'], headers=self.headers).json()
        n = 1
        # If the submission has a name print the name, else print the
        for submission in submissions['_embedded']['submissions']:
            if 'name' in submission:
                print(f"{n} - Name: {submission['name']}")
            else:
                print(f"{n} - Submission uuid:{submission['_links']['self']['href'].split('/')[-1]}")
            n += 1
        submission_index = int(input("Please select a number: ")) - 1
        self.submission = rq.get(submissions['_embedded']['submissions'][submission_index]['_links']['self']['href'],
                                 headers = self.headers).json()

    def _navigate_api(self):
        if not self.current_link:
            self.current_link = self.root
        links = rq.get(self.current_link, headers=self.headers).json()['_links']
        n = 1
        print("Please choose one of the following by number")
        for api_part, href in links.items():
            print(f"{n} - {api_part}")
            n += 1
        try:
            next_link = int(input("Please select a number (If no number, navigation will stop): "))
            self.current_link = list(links.values())[next_link - 1]['href']
            self._navigate_api()
        except ValueError:
            return

    def _retrieve_submission_content(self):
        if not self.submission:
            print("No submission was selected. Redirecting to select submission:")
            self.select_submission()
        self.submission_content = rq.get(f"{self.submission['_links']['contents']['href']}", headers=self.headers).json()

    def show_submission_status(self):
        self._retrieve_submission_status()
        pprint(f"The submission status for submission with ID {self.submission.get('id')} is {self.submission_status}")

    def _retrieve_submission_status(self):
        if not self.submission:
            print("No submission was selected. Redirecting to select submission:")
            self.select_submission()
        submission_status_json = rq.get(self.submission['_links']['submissionStatus']['href'], headers=self.headers).json()
        self.submission_status = submission_status_json['status']

    def _retrieve_samples(self):
        self._retrieve_submission_content()
        samples = rq.get(self.submission_content['_links']['samples']['href'], headers=self.headers).json()
        self.samples = samples['_embedded']['samples']

    def show_sample_information(self):
        if not self.samples:
            self._retrieve_samples()
        newline = '\n'
        pprint(f"For submission with ID {self.submission['id']}, samples are:\n"
               f"{newline.join([sample['alias'] for sample in self.samples])}")

    def _retrieve_studies(self):
        if not self.submission_content:
            self._retrieve_submission_content()
        studies = rq.get(self.submission_content['_links']['enaStudies']['href'], headers=self.headers).json()
        self.studies = studies['_embedded']['enaStudies']

    def show_study_information(self):
        if not self.studies:
            self._retrieve_studies()
        newline = '\n'
        pprint(f"For submission with ID {self.submission['id']}, studies are:\n"
               f"{newline.join([study['alias'] for study in self.studies])}")

    def submit_submittable(self, submittable_type, json_content):
        if not self.submission_status:
            self._retrieve_submission_status()
        if self.submission_status == 'Completed':
            print("This submission is already completed. Please select another or change the status")
            return
        self._retrieve_submission_content()

        # Sanity check for submission types
        while True:
            if not any([submittable_type == accepted_type for accepted_type in self.accepted_submission_types]):
                print(f"Please select a number of one of the accepted submittable types from this list:")
                for i in range(len(list(self.accepted_submission_types.keys()))):
                    print(f"{i + 1} - {list(self.accepted_submission_types.keys())[i]}")
                submittable_type_index = int(input()) - 1
                if 0 < submittable_type_index < len(list(self.accepted_submission_types.keys())):
                    submittable_type = self.accepted_submission_types[list(self.accepted_submission_types.keys())[submittable_type_index]]
                    break
                else:
                    print("Please select a valid number")
            else:
                break


        # Create the submission
        create_submittable_url = self.submission_content['_links'][f'{submittable_type}:create']['href']
        new_submission = rq.post(url=create_submittable_url, json=json_content, headers=self.headers)

        if not new_submission.status_code < 210:
            print(f"An error ocurred while submitting. Error:\n{new_submission.json()}")
        else:
            print("Submission successfully done!")
            self._update_token()

    def replace_project(self, project_json_content):
        self._retrieve_submission_content()
        project = rq.get(self.submission_content['_links']['project']['href'], headers=self.headers).json()
        replace_project_url = project['_links']['self:update']['href']
        rq.put(replace_project_url,data=project_json_content, headers=self.headers)
        self._update_token()

    def delete_project(self):
        self._retrieve_submission_content()
        project = rq.get(self.submission_content['_links']['project']['href'], headers=self.headers).json()
        delete_project_url = project['_links']['self:delete']['href']
        rq.delete(delete_project_url, headers=self.headers)
        self._update_token()

    def _retrieve_project_info(self):
        if not self.submission_content:
            self._retrieve_submission_content()
        self.current_project = rq.get(self.submission_content['_links']['project']['href'], headers=self.headers).json()

    def show_validation_results(self):
        self._retrieve_validation_results()
        newline_tab = '\n\t'
        i = 1
        for result in self.validation_results['_embedded']['validationResults']:
            validation_result = rq.get(result['_links']['self']['href'], headers=self.headers).json()
            submittable = rq.get(validation_result['_links']['submittable']['href'], headers=self.headers).json()
            print(f"{i} - For sample with alias {submittable['alias']}, validation results are as following:\n"
                  f"{newline_tab.join([f'{key}:{value}' for key, value in result['overallValidationOutcomeByAuthor'].items()])}")
            i += 1

    def _retrieve_validation_results(self):
        if not self.submission:
            self.select_submission()
        self.validation_results = rq.get(self.submission['_links']['validationResults']['href'], headers=self.headers).json()

    #TODO Add check for if submission is invalid
    def finish_submission(self):
        self._update_token()
        url_to_submit = self.submission['_links']['submissionStatus']['href']
        response = rq.put(url_to_submit, data='{"status" : "Submitted"}', headers=self.headers)
        pprint(response.json())
        self._update_token()

    def submit_directory(self, directory):
        if not os.path.exists(directory):
            print("The provided directory doesn't exist")
        for (dirpath, dirnames, filenames) in os.walk(directory):
            files = filenames
            break
        files = [f"{directory}/{file}" for file in files if file.endswith('.json')]
        for file in files:
            submission_type = file.split('/')[-1].split('_')[0]
            with open(file, "r") as f:
                submission = js.loads(f.read())
            self.submit_submittable(submission_type, submission)
            #submission_function = getattr(self, f"submit_new_{submission_type}")
            #submission_function(submission)
            self._update_token()
        self._update_token()

    def _retrieve_processing_statuses(self):
        if not self.submission:
            self.select_submission()
            self._retrieve_submission_status()

        if not self.submission_status == 'Completed':
            self.processing_status = 'Submission is not completed, therefore no processing status can be retrieved'
        else:
            self.processing_status = rq.get(self.submission['_links']['processingStatuses']['href'], headers=self.headers).json()

    def show_processing_statuses(self):
        if not self.processing_status:
            self._retrieve_processing_statuses()

        pprint(self.processing_status)
        print(f"For submission with ID {self.submission['id']}, processing statuses are:\n")
        for status in self.processing_status['_embedded']['processingStatuses']:
            print(f"{status['submittableType']}: alias {status['alias']}:")
            print(f"\tStatus: {status['status']}")
            print(f"\tArchive: {status['archive']}")
            print(f"\tAccession: {status.get('accession')}\n")



    def _back_to_root_api(self):
        self.current_link = self.root

# TODO add retrieve_schemas and show_schemas