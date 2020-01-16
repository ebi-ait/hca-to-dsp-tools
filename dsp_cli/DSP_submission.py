import requests as rq
from pprint import pprint
import os
import json as js

class DspCLI():
    def __init__(self):
        self.user, self.password,self.root = self.retrieve_credentials()
        self.token = self.retrieve_token()
        self.team_url = f"{self.root}user/teams/"
        self.headers = {'Content-Type': 'application/json;charset=UTF-8', 'Accept': 'application/hal+json',
                        'Authorization': f'Bearer {self.token}'}
        self.submission = ''
        self.team = ''
        self.current_link = ''
        self.submission_content = ''
        self.submission_status = ''
        self.current_project = ''
        self.current_project_status = ''

    def list_submissions(self):
        return rq.get(f'{self.root}user/submissions', headers=self.headers).json()

    def retrieve_token(self):
        dev='explore.' if '-test' in self.root else ''
        return rq.get(f"https://{dev}api.aai.ebi.ac.uk/auth", auth=(self.user, self.password)).text.strip()

    def update_token(self):
        self.token = self.retrieve_token()
        self.headers = {'Content-Type': 'application/json;charset=UTF-8', 'Accept': 'application/hal+json',
                        'Authorization': f'Bearer {self.token}'}
        self.retrieve_submission_content()

    def retrieve_credentials(self):
        with open('cred.txt', 'r') as f:
            user = f.readline().split('=')[-1].strip()
            password = f.readline().split('=')[-1].strip()
            root = f.readline().split('=')[-1].strip()
        return user, password,root

    def create_new_team(self, description, centreName):
        post = {'description': description, 'centreName': centreName}
        response = rq.post(self.team_url, json=post, headers=self.headers)
        # Every time a new team is created we need to update the token and therefore the headers
        self.token = self.retrieve_token()
        self.headers = {'Content-Type': 'application/json', 'Accept': 'application/hal+json',
                        'Authorization': f'Bearer {self.token}'}
        return response.json()

    def create_empty_submission(self, team, name=''):
        json = {} if not name else name
        if isinstance(team, dict):
            url = team['_links']['submissions:create']['href']
        else:
            url = team
        self.submission = rq.post(url=url, json=json, headers=self.headers).json()

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

    def navigate_api(self):
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
            self.navigate_api()
        except ValueError:
            return

    def retrieve_submission_content(self):
        if not self.submission:
            print("No submission was selected. Redirecting to select submission:")
            self.select_submission()
        self.submission_content = rq.get(f"{self.submission['_links']['contents']['href']}", headers=self.headers).json()

    def retrieve_submission_status(self):
        if not self.submission:
            print("No submission was selected. Redirecting to select submission:")
            self.select_submission()
        submission_status_json = rq.get(self.submission['_links']['submissionStatus']['href'], headers=self.headers).json()
        self.submission_status = submission_status_json['status']


    def submit_new_samples(self, sample_json_content):
        if not self.submission_status:
            self.retrieve_submission_status()
        if self.submission_status == 'Completed':
            print("This submission is already completed. Please select another or change the status")
        self.retrieve_submission_content()
        create_sample_url = self.submission_content['_links']['samples:create']['href']
        new_sample_submission = rq.post(url=create_sample_url, json=sample_json_content, headers=self.headers)
        if not new_sample_submission.status_code == 200:
            print(f"An error ocurred while submitting the sample. Error:\n{new_sample_submission.json()}")
        else:
            self.update_token()

    def submit_new_project(self, project_json_content):
        if not self.submission_status:
            self.retrieve_submission_status()
        if self.submission_status == 'Completed':
            print("This submission is already completed. Please select another or change the status")
        self.retrieve_submission_content()
        create_project_url = self.submission_content['_links']['projects:create']['href']
        new_project_submission = rq.post(url=create_project_url, json=project_json_content, headers=self.headers)
        if not new_project_submission == 200:
            print(f"An error ocurred while submitting the project. Error:\n{new_project_submission.json()}")
        else:
            self.update_token()

    def submit_new_study(self, study_json_content):
        self.retrieve_submission_content()
        create_study_url = self.submission_content['_links']['enaStudies:create']['href']
        new_study_submission = rq.post(url=create_study_url, json=study_json_content, headers=self.headers)
        if not new_study_submission == 200:
            print(f"An error ocurred while submitting the project. Error:\n{new_study_submission.json()}")
        else:
            self.update_token()

    def submit_new_assay(self, assay_json_content):
        self.retrieve_submission_content()
        create_study_url = self.submission_content['_links']['studies:create']['href']
        new_study_submission = rq.post(url=create_study_url, json=assay_json_content, headers=self.headers)
        if not new_study_submission == 200:
            print(f"An error ocurred while submitting the project. Error:\n{new_study_submission.json()}")
        else:
            self.update_token()

    def replace_project(self, project_json_content):
        self.retrieve_submission_content()
        project = rq.get(self.submission_content['_links']['project']['href'], headers=self.headers).json()
        replace_project_url = project['_links']['self:update']['href']
        rq.put(replace_project_url,data=project_json_content, headers=self.headers)
        self.update_token()

    def delete_project(self):
        self.retrieve_submission_content()
        project = rq.get(self.submission_content['_links']['project']['href'], headers=self.headers).json()
        delete_project_url = project['_links']['self:delete']['href']
        rq.delete(delete_project_url, headers=self.headers)
        self.update_token()

    def retrieve_project_info(self):
        if not self.submission_content:
            self.retrieve_submission_content()
        self.current_project = rq.get(self.submission_content['_links']['project']['href'], headers=self.headers).json()

    def retrieve_project_status(self):
        if not self.current_project:
            self.retrieve_project_info()
        self.current_project_status = rq.get(self.current_project['_links']['validationResult']['href'], headers=self.headers).json()

    def finish_submission(self):
        self.update_token()
        if not self.current_project:
            self.retrieve_project_info()
        url_to_submit = self.current_project['_embedded']['submission']['_links']['submissionStatus']['href']
        response = rq.put(url_to_submit, data='{"status" : "Submitted"}', headers=self.headers)
        pprint(response.json())
        self.update_token()

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
            submission_function = getattr(self, f"submit_new_{submission_type}")
            submission_function(submission)
        self.update_token()
    def back_to_root_api(self):
        self.current_link = self.root