import requests as rq
from pprint import pprint
import os
import json as js
from tusclient import client
import sys
from tqdm import tqdm

# TODO Create delete_submission()
# TODO Create detect_validation_errors()
# TODO add change_release_date()
# TODO add retrieve_schemas and show_schemas

class DspCLI():
    def __init__(self):
        self.headers = ""
        self.user, self.password, self.root_url = self._retrieve_credentials()
        self.root = self._get(self.root_url).json().get('_links')
        self.token = ''
        self._retrieve_token()
        self.team_url = f"{self.root_url}user/teams/"
        self.headers = {'Content-Type': 'application/json;charset=UTF-8', 'Accept': 'application/hal+json',
                        'Authorization': f'Bearer {self.token}'}
        self.accepted_submission_types = {"projects": "projects",
                                          "samples": "samples",
                                          "study": "enaStudies",
                                          "assays": "sequencingExperiments",
                                          "assay_data": "sequencingRuns"}
        self.accepted_retrieval_types = {"projects": "projects",
                                          "samples": "samples",
                                          "enaStudies": "studies",
                                          "sequencingExperiments": "assays",
                                          "sequencingRuns": "assayData"}
        self.submission = ''
        self.submittables = {}
        self.team = ''
        self.current_link = ''
        self.submission_content = ''
        self.submission_status = ''
        self.current_project = ''
        self.current_project_status = ''
        self.studies = ''
        self.validation_results = ''
        self.processing_status = ''
        self.client = ''

    # ----------------- #
    # Wrapper functions #
    # ----------------- #

    def _get(self, url: str, **kwargs: any((dict, tuple))) -> any((rq.Response, None)):
        """
        Wrapper function for requests.get. Avoids token expiration and adds headers if already present in object.

        :parameter url : str
                         URL to send the get request to
        :parameter kwargs : dict
                            Keyword arguments to pass to requests.get

        :returns response : requests.Response
                            Response to the get request
        :returns None : None
                        If no url is provided, it will return None (To handle by the method that calls the function)
        """
        # Add headers to kwargs if they don't exist
        if self.headers:
            kwargs['headers'] = self.headers

        # If endpoint of the API is not found, url will be `''` and will throw a MissingSchema exception.
        try:
            response = rq.get(url, **kwargs)
        except rq.exceptions.MissingSchema:
            return None

        # Unauthorised request
        if response.status_code == 401:
            if "aai" not in url:
                self._update_token()
                response = rq.get(url, **kwargs)
            else:
                print(f"GET request to URL {url} has been unauthorised.\n"
                      f"Please ensure you're sending the proper credentials in the header.\n"
                      f"Keyword arguments used in header: {kwargs}")

        return response

    def _post(self, url: str, data: dict, **kwargs: dict) -> rq.Response:
        """
        Wrapper function for requests.post. Avoids token expiration and adds headers if already present in object.

        :parameter url : str
                         URL to send the post request to
        :parameter data : dict
                          JSON data in the form of a python dictionary
        :parameter kwargs : dict
                            Keyword arguments to pass to requests.post

        :returns response : requests.Response
                            Response to the post request.
        :returns None : None
                        If no url is provided, it will return None (To handle by the method that calls the function)
        """
        # Add headers to kwargs if they don't exist
        if self.headers:
            kwargs['headers'] = self.headers

        # If endpoint of the API is not found, url will be `''` and will throw a MissingSchema exception.
        try:
            response = rq.post(url, js.dumps(data), **kwargs)
        except rq.exceptions.MissingSchema:
            return None

        # Unauthorised request
        if response.status_code == 401:
            self._update_token()
            response = rq.post(url, data, headers=self.headers)

        # Malformed JSON Request
        if response.status_code == 400:
            pprint(f"There was an error with the request. Please make sure that the data is a json-valid object"
                   f"(python dictionary). Data sent: {data}")

        # Update token if POST request was successful
        if response.status_code == 200:
            self._update_token()
            if self.submission:
                self._update_submission()

        return response

    def _put(self, url: str, data: str, **kwargs: dict):
        """
        Wrapper function for requests.put
        - Avoids token expiration
        - Adds headers if already present in object
        - If malformed JSON request, tries to convert data into a string with method json.dumps()

        :parameter url : str
                         URL to send the put request to
        :parameter data : str
                          JSON data in the form of a string
        :parameter kwargs : dict
                            Keyword arguments to pass to `requests.post`

        :returns response : requests.Response
                            Response to the put request.
        :returns None : None
                        If no url is provided, it will return None (To handle by the method that calls the function)
        """
        # Add headers to kwargs if they don't exist
        if self.headers:
            kwargs['headers'] = self.headers

        # If endpoint of the API is not found, url will be `''` and will throw a MissingSchema exception.
        try:
            response = rq.put(url, data, **kwargs)
        except rq.exceptions.MissingSchema:
            return None

        # Unauthorised request
        if response.status_code == 401:
            self._update_token()
            response = rq.put(url, data, headers=self.headers)

        # Malformed JSON request
        if response.status_code == 400:
            response = rq.put(url, data=js.dumps(data), headers=self.headers)

        # Update token if POST request was successful
        if response.status_code == 200:
            self._update_token()
            if self.submission:
                self._update_submission()

        return response

    def _delete(self, url: str, **kwargs: dict) -> rq.Response:
        """
        Wrapper function for `requests.delete`.
        - Updates token if expired
        - Updates token if successful
        :parameter url : str
                         URL to send the put request to
        :parameter kwargs : dict
                            Keyword arguments to pass to `requests.post`

        :returns response : requests.Response
                            Response to the put request.
        :returns None : None
                        If no url is provided, it will return None (To handle by the method that calls the function)
        """
        # Add headers to kwargs if they don't exist
        if self.headers and 'headers' not in kwargs:
            kwargs['headers'] = self.headers

        # If endpoint of the API is not found, url will be `''` and will throw a MissingSchema exception.
        try:
            response = rq.delete(url, **kwargs)
        except rq.exceptions.MissingSchema:
            return None

        # Unauthorised request
        if response.status_code == 401:
            self._update_token()
            response = rq.delete(url, headers=self.headers)

        # Update token if DELETE request was successful. Update submission deleting anything from a submission.
        if response.status_code == 204:
            self._update_token()
            if self.submission:
                self._update_submission()

        return response
    # ------------------ #
    # \Wrapper methods   #
    # ------------------ #
# TODO ADD UPDATE_SUBMITTABLE -> Fields (update_field_submittable) and replace (replace_submittable)
    # ------------------ #
    #   Hidden methods   #  */ Methods mostly about retrieving attributes and updating tokens/attributes
    # ------------------ #

    def _select_index(self) -> int:
        """
        Select a number from a 1-indexed array and return the proper index. Also sanity checks for integer
        :returns index : int
                         Integer representing the value in a 0-indexed array
        """
        while True:
            try:
                index = int(input("Please select a number: ")) - 1
                break
            except ValueError:
                print("Please input a valid integer or press <ctrl> + <c> to exit")
        return index

    def _check_submittable_type(self, submittable_type: str) -> str:
        """
        Internal method to check that the submittable type selected is valid.
        :param submittable_type : str
                                 Submittable type
        :returns submittable_type : str
                                    Accepted submittable type
        """
        # Make sure the proper submittable_type is used
        if submittable_type not in self.accepted_submission_types.values():
            while True:
                print("Please select one of the accepted submittable types")
                self.show_accepted_submittables()
                index = self._select_index()
                if 0 <= index < len(list(self.accepted_submission_types.keys())):
                    submittable_type = list(self.accepted_submission_types.values())[index]
                    return submittable_type
                else:
                    print("Please introduce a valid integer")
        return submittable_type

    def _check_submission_availability(self) -> any((None, False)):
        """
        Internal method to check submission availability before submission.
        :returns False or True : boolean
                                 Return boolean based on submission availability
        """
        # Load a submission if not already loaded
        if not self.submission:
            self.select_submission()

        # If the submission is completed you can't submit anything.
        if self.submission_status == 'Completed':
            return False

        return True

    def _check_submission_blockers(self):
        submission_blockers = self._get(self.submission.get('_links', {}).get('submissionBlockersSummary', {}).get('href')).json()
        results = [value for key, value in submission_blockers.items() if not key.startswith("_") and not isinstance(value, dict)]
        return any([result == True or result > 0 for result in results])

    def _check_json_content(self, json_content: any((str, dict))) -> any((dict, bool)):
        """
        Check the JSON content for a submittable is a dictionary. Also check if it's a string representation of a
        JSON or a file.
        :param json_content: str or dict
                             If dict, it will just return the dictionary. If str, will check for JSON in string format
                             or
        :returns json_content or False : dict or bool
                                         Content of the JSON in a dictionary form or a boolean if nothing could be
                                         found
        """
        # If the `json_content` provided is not a dictionary, check if it's a json string or a file path
        if isinstance(json_content, str):
            try:
                json_content = js.loads(json_content)
            except js.decoder.JSONDecodeError:
                if not os.path.exists(json_content):
                    print("The provided path to the file doesn't exist")
                    return False
                with open(json_content, 'r') as f:
                    json_content = js.load(f)

        return json_content

    def _retrieve_files(self) -> list:
        """
        Internal method to retrieve the files given a submission is set.
        :returns files : list
                         List of files available for the submission
        """
        response = self._get(f"{self.root_url}files/search/by-submission?submissionId={self.submission.get('id')}").json()
        files = response.get('_embedded', {}).get('files')
        total_pages = response.get('page', {}).get('totalPages') - 1
        for _ in range(total_pages):
            response = self._get(response.get('_links', {}).get('next', {}).get('href'))
            files.extend(response.get('_embedded', {}).get('files'))

        return files

    #TODO _retrieve_files()

    def _retrieve_submittable_same_alias(self, submittable_list: list, alias: str, key_to_search: str = 'alias') -> dict:
        for submittable in submittable_list:
            if submittable.get(key_to_search) == alias:
                return submittable
        return False

    def _retrieve_processing_statuses(self) -> any((rq.Response, None)):
        """
        Retrieve the processing statuses for a submission. Will fail if submission is not completed.
        :returns response or None : requests.Response or None
                                    response for the get request or None if submission is not finished.
        """
        if self._check_submission_availability():
            self.processing_status = 'Submission is not completed, therefore no processing status can be retrieved'
            return None
        else:
            response = self._get(self.submission.get('_links', {}).get('processingStatuses', {}).get('href', {}))
            self.processing_status = response.json()

        return response

    def _retrieve_token(self) -> None:
        """
        Given `self.user`, `self.password` and `self.root` have been set up, retrieve a token from the AAP and set
        `self.token`.
        """
        self.token = self._get(f"{self.root.get('aap-api-root', {}).get('href')}/auth",
                               auth=(self.user, self.password)).text.strip()

    def _update_token(self) -> None:
        """
        Update the token in case it expires and update the headers to reflect the new token
        """
        self._retrieve_token()
        self.headers = {'Content-Type': 'application/json;charset=UTF-8', 'Accept': 'application/hal+json',
                        'Authorization': f'Bearer {self.token}'}

    def _retrieve_submission(self) -> None:
        """
        Update `self.submission`. Should only be called if a submission is already loaded.
        """
        self.submission = self._get(self.submission.get('_links', {}).get('self', {}).get('href')).json()

    def _retrieve_submission_content(self):
        """
        Retrieve the API root for the contents of a submission.
        """
        self.submission_content = self._get(self.submission.get('_links', {}).get('contents', {}).get('href', {})).json()

    def _retrieve_submission_status(self):
        """
        Retrieve the status for a submission (Draft, Completed)
        """
        submission_status_json = self._get(self.submission.get('_links', {}).get('submissionStatus', {}).
                                           get('href')).json()
        self.submission_status = submission_status_json.get('status')

    def _update_submission(self) -> None:
        """
        Update all the attributes related to a submission. Only to be called when modifying a submission.
        """
        self._retrieve_submission()
        self._retrieve_submission_content()
        self._retrieve_submission_status()

    def _retrieve_credentials(self) -> (str, str, str):
        """
        Retrieve the credentials for AAP login from cred.txt

        :return user : str
                       Username for the EBI AAP
        :return password : str
                           Password for the EBI AAP
        :return root : str
                       Root URL for the DSP API
        """
        with open('cred.txt', 'r') as f:
            user = f.readline().split('=')[-1].strip()
            password = f.readline().split('=')[-1].strip()
            root = f.readline().split('=')[-1].strip()
        return user, password, root

    def _retrieve_submittables(self, submittable_type: str) -> any((list, None)):
        """
        Internal method to retrieve the submittables for a submission.

        :param submittable_type : str
                                 Submittable type from the ones accepted in the list.
        :returns self.submittables[submittable_type] : list
                                                       list of submittables for the submission
        """
        # Update submission to make sure all the submittables can be loaded.
        self._update_submission()

        retrieval_type = self.accepted_retrieval_types[submittable_type]

        submittables = self._get(self.submission_content.get('_links', {}).get(submittable_type).get('href')).json()
        self.submittables[submittable_type] = submittables.get('_embedded', {}).get(retrieval_type)

        # Deal with paginated answer
        if self.submittables[submittable_type]:
            while True:
                submittables = self._get(submittables.get('_links', {}).get('next', {}).get('href'))
                if not submittables:
                    break
                submittables = submittables.json()
                self.submittables[submittable_type].extend(submittables.get('_embedded', {}).get(retrieval_type))

        # Return a list of the submittables of the `submittable_type`.
        return self.submittables[submittable_type]

    def _retrieve_validation_results(self) -> list:
        """
        Internal method to retrieve the validation results for a submission.
        :returns validation_results : list
                                      list with all the validationResults from all the pages.
        """
        # Retrieve validation results
        validation_results_page = self._get(self.submission.get('_links', {}).get('validationResults', {}).get('href')).json()
        total_pages = validation_results_page.get('page', {}).get('totalPages', 1)
        validation_results = validation_results_page.get('_embedded', {}).get('validationResults')

        # Deal with pagination
        for _ in range(total_pages - 1):
            validation_results_page = self._get(
                validation_results_page.get('_links', {}).get('next', {}).get('href')).json()
            validation_results.extend(validation_results_page.get('_embedded', {}).get('validationResults'))

        return validation_results

    # ------------------ #
    #   Basic methods    #
    # ------------------ #

    def create_new_team(self, description: str, centre_name: str) -> any((rq.Response, None)):
        """
        Create a new team for the user.
        :param description : str
                             Brief description of the team
        :param centre_name : str
                             Name of the centre of the submission (e.g. EBI)
        :returns response : requests.Response
                            Response object from requests module
        """
        team = {'description': description, 'centreName': centre_name}

        # Get the URL for teams from the API root
        response = self._post(self.root.get('userTeams').get('href'), data=team, headers=self.headers)

        if not response:
            print("Team could not be created. Please check the root URL provided is alright")

        # Every time a new team is created we need to update the token and therefore the headers
        self._update_token()

        return response

    def create_submission(self, name: str = '') -> any((None, rq.Response)):
        """
        Create an empty submission within the selected team.
        :param name: str
                     Name of the submission. If not specified the submission will be identified by its UUID.
        :returns response : requests.Response
                            Response object from requests module
        """
        # If there is no team selected, select team.
        if not self.team:
            self.select_team()

        # Name has to be supplied as a key:pair value. Conversion for user friendliness.
        name = {} if not name else {'name': name}
        create_url = self.team.get('_links', {}).get('submissions:create', {}).get('href')
        # Try-catch for creating a submission that doesn't exist
        try:
            response = self._post(url=create_url, data=name, headers=self.headers)
        except rq.exceptions.MissingSchema:
            print(f"This user can't create a submission on team {self.team.get('name')}")
            return response

        # Set up submission attribute and update the token with the headers
        self.submission = response.json()
        self._update_token()

        return response

    def show_accepted_submittables(self) -> None:
        """
        Print accepted submittables to the user
        """
        for index, submittable in enumerate(self.accepted_submission_types.keys()):
            print(f"{index + 1} - {submittable}")

    def show_submissions(self) -> any((list, None)):
        """
        Shows the available submissions for a team. If no team has been selected, calls `self.select_team()` first.
        :returns submission_list : list or None
                                   list of submission responses. Will return `None` if there are no submissions

        """
        # Select a team before showing available submissions
        if not self.team:
            self.select_team()

        # Retrieve submission list and exit if there are no submissions
        submission_list = self._get(self.team.get('_links', {}).get('submissions', {}).get('href')).json()
        if not submission_list:
            print(f"There are no submissions available for the user on team '{self.team.get('name')}'")
            return submission_list

        # Print the available submissions to the user
        print(f"Submissions available for team '{self.team.get('name')}' are the following:")
        for index, submission in enumerate(submission_list.get('_embedded', {}).get('submissions')):
            # Print either the name or the ID of the submission
            if 'name' in submission:
                print(f"{index + 1} - Name: {submission['name']}")
            else:
                print(f"{index + 1} - Submission uuid: {submission['_links']['self']['href'].split('/')[-1]}")

        # Return submission list for external purposes
        return submission_list.get('_embedded', {}).get('submissions')

    def show_teams(self) -> list:
        """
        Show the teams available to the user
        :returns
        """
        # Retrieve a list of available teams
        teams_url = self.root.get('userTeams').get('href')
        team_list = self._get(teams_url, headers=self.headers).json()

        # Print the names (or UUIDs) to the user.
        print("The teams are the following:")
        for index, team in enumerate(team_list.get('_embedded', {}).get('teams')):
            print(f"{index + 1} - {team.get('name')}")

        # Return the list of teams for other purposes outside of the function
        return team_list.get('_embedded', {}).get('teams')

    def select_team(self) -> any((dict, None)):
        """
        Select a team to work in. Teams correspond to domains in the EBI AAP.

        :return self.team : dict
                            Dictionary containing the JSON contents for the selected team
                teams : None
                        If there are no teams it will return None
        """
        # Show which teams are available
        teams = self.show_teams()
        if not teams:
            print("There are no teams available for the user. Please create one or ask to be added to a team")
            return teams

        # Sanity check for integer inputs
        team_index = self._select_index()

        # Set up current team based on user input
        self.team = teams[team_index]

        # Return team for external purposes
        return self.team

    def select_submission(self) -> any((dict, None)):
        """
        Select a submission within a team to work in.
        :returns self.submission : dict or None
                                   JSON representation of root of selected submission or None if no submissions
                                   available
        """
        # Select team if none has been selected. Exit if there are no teams available
        if not self.team:
            teams = self.select_team()
            if not teams:
                return

        # Show which submissions are available
        submissions = self.show_submissions()

        # Sanity check for integer inputs
        submission_index = self._select_index()

        # Retrieve the submission and set attribute.
        self.submission = self._get(submissions[submission_index].get('_links', {}).get('self', {}).get('href')).json()

        # If there is a submission, update the content and status.
        if self.submission:
            self._update_submission()

        # Return submission for external purposes.
        return self.submission

    def show_submission_status(self) -> str:
        """
        Print and return the status of a submission. Status can be Draft, Submitted.
        :returns self.submission_status : str
                                          Submission status.
        """
        # Return None if no submission has been selected.
        if not self.submission:
            print("Please select a submission first")
        else:
            self._retrieve_submission_status()
            print(f"The submission status for submission with ID {self.submission.get('id')} is {self.submission_status}")
        return self.submission_status

    def show_submittable_names(self, submittable_type: str = ""):
        """
        Show the names of the submittables of a certain submittable type in a submission.
        :param submittable_type : str
                                  Submittable type. Optional as it can be chosen within the method by manual input.
        :returns submittables : list
                                List of submittables for that submittable type in the selected submission.
        """
        # Return None if no submission has been selected.
        if not self.submission:
            print("Please select a submission first")
            return None

        # Check it is an accepted submittable type
        submittable_type = self._check_submittable_type(submittable_type)

        # Retrieve the submittables of that type for the submission
        print(f"Retrieving all {submittable_type}. This might take a while...")
        submittables = self._retrieve_submittables(submittable_type)
        if not submittables:
            return None

        # Print the results to the user. Ask first because there can be many of them
        show = input(f"There are {len(submittables)} {submittable_type}. "
                     f"Are you sure you want to print them all?[Y/n]\n")
        if not show or "y" in show.lower():
            newline = "\n"
            print(f"For submission with ID {self.submission.get('id')}, {submittable_type} files are:\n"
                  f"{newline.join([submittable.get('alias') for submittable in self.submittables.get(submittable_type)])}")

        # Return the list of submittables
        return submittables

    def create_submittable(self, json_content: any((str, dict)),  submittable_type: str = "") -> any((rq.Response, None)):
        """
        Creates a submittable given JSON dictionary with the contents of the submittable
        :param json_content : dict or str
                              JSON content in the form of a python dictionary. A string can be provided and it will be
                              treated as a file path
        :param submittable_type : str
                                  Submittable type. Optional as it can be chosen within the method by manual input.
        :returns new_submittable : requests.Response or None
                                   Response object containing the response for the new submission or None if
                                   submission is completed or JSON file was not found.
        """
        # Check submission availability
        if not self._check_submission_availability():
            return None

        # Check the JSON content and return None if failing
        json_content = self._check_json_content(json_content)
        if not json_content:
            return None

        # Sanity check for submission types
        submittable_type = self._check_submittable_type(submittable_type)

        # Create the submission. Status code is checked within the wrapped post method
        create_submittable_url = self.submission_content.get('_links', {}).get(f'{submittable_type}:create', {}).get(
            'href')
        new_submittable = self._post(url=create_submittable_url, data=json_content, headers=self.headers)

        # Check the status code of the response
        if new_submittable.status_code < 210:
            print(f"Creation of {submittable_type} {json_content.get('alias')} was successful!")

        return new_submittable

    def replace_submittable(self, json_content: any((str, dict)), submittable_type: str = "") -> any((None, rq.Response)):
        """
        Replaces a submittable given a JSON dictionary with the contents of the submittable
        :param json_content : dict or str
                              JSON content in the form of a python dictionary. A string can be provided and it will be
                              treated as a file path
        :param submittable_type : str
                                  Submittable type. Optional as it can be chosen within the method by manual input.
        :returns replaced_submittable : requests.Response or None
                                        Response object containing the response for the replacement. None if submission
                                        is completed or JSON file was not found.
        """
        # Check submission availability
        if not self._check_submission_availability():
            return None

        # Check the JSON content and return None if failing
        json_content = self._check_json_content(json_content)
        if not json_content:
            return None

        # Sanity check for submission types
        submittable_type = self._check_submittable_type(submittable_type)

        # Retrieve submittable objects
        submittable_list = self._retrieve_submittables(submittable_type)

        # Parse the submittable list to find the submittable with the same alias as the one provided and replace it.
        submittable = self._retrieve_submittable_same_alias(submittable_list, json_content.get('alias'))
        if not submittable:
            print(f"Couldn't find submittable with alias {json_content.get('alias')} in current submission")
            return None
        else:
            replace_url = submittable.get('_links', {}).get('self:update', {}).get('href')
            replaced_submittable = self._put(replace_url, json_content)
            if replaced_submittable.status_code < 210:
                print(f"Replacement of {submittable_type} {json_content.get('alias')} was successful!")
            return replaced_submittable

    def delete_submittable(self, submittable_type: str, alias: str = ""):
        """
        Deletes a submittable. Alias is optional but helps find the submittable.
        :param submittable_type : str
                                  Submittable type. Optional as it can be chosen within the method by manual input.
        :param alias : str
                       Alias of the submittable in the submission. Optional.
        :returns deleted_submittable : requests.Response or None
                                       Response object containing the response for the deletion. None if submission
                                       is completed or submittable was not found.
        """
        # Check submission availability
        if not self._check_submission_availability():
            return None

        # Sanity check for submittable types
        submittable_type = self._check_submittable_type(submittable_type)

        # Retrieve submittable objects
        submittable_list = self._retrieve_submittables(submittable_type)

        # Retrieve the submittable to delete
        if alias:
            submittable = self._retrieve_submittable_same_alias(submittable_list, alias)
        else:
            # Let the user decide how many submittables wants to print in screen at once
            while True:
                try:
                    step = int(input("Aliases are going to be printed with a number. Please select how many do you want to"
                                     "print at once in screen"))
                    break
                except ValueError:
                    print("Please input a valid integer or press <ctrl> + <c> to exit")

            # Parse the submittables
            start = 0
            stop = step
            index = -1
            while start < len(submittable_list):
                print("Available {submittable_type} below. Please select '0' if you don't see your submittable")
                for i in range(start, stop):
                    print(f"{i + 1} - {submittable_list[i].get('alias')}")
                start = i + 1
                stop += step
                if stop >= len(submittable_list):
                    stop = len(submittable_list)
                index = self._select_index()
                if index >= 0:
                    break

            # Delete the submittable or inform the user about not finding the submittable
            if index < 0:
                print("All submittables have been printed. Please make sure you're in the right submission")
                return None
            else:
                submittable = submittable_list[index]
                delete_url = submittable.get('_links', {}).get('self:delete', {}).get('href')
                deleted_submittable = self._delete(delete_url)
                if deleted_submittable.status_code == 204:
                    print(f"Submittable {submittable.get('alias')} was deleted successfully")
                return deleted_submittable

    def show_validation_results(self) -> list:
        """
        Show all validation results for a submission

        :returns validation_results : list or None
                                      list of all the validation results. If submission is not available, return None.
        """
        # Only show validation results for uncompleted submissions
        if not self._check_submission_availability():
            return None

        # Retrieve validation results
        validation_results = self._retrieve_validation_results()

        # If there are more than 20 validation results, give the user the opportunity to write the output to a log
        write_to = sys.stdout
        if len(validation_results) > 20:
            print(f"There are {len(validation_results)} validation results available. Want to:\n"
                  f"1 - Print to screen\n2 - Save to log")
            index = self._select_index()
            if index != 0:
                filename = f"validation_results_{self.submission.get('name')}.txt"
                print(f"Output will be saved to {filename}")
                write_to = open(filename, "w")

        # Retrieve the validation results. Extracting the alias along requires extra steps
        for index, result in enumerate(validation_results):
            validation_result = self._get(result.get('_links', {}).get('self', {}).get('href'))
            if not validation_result:
                continue
            validation_result = validation_result.json()
            newline_tab = '\n\t\t'
            if 'submittable' in validation_result['_links']:
                submittable = self._get(validation_result['_links']['submittable']['href'], headers=self.headers).json()
                write_to.write(f"{index + 1} - For submittable with alias {submittable['alias']}, validation results are as following:\n"
                      f"\t\t{newline_tab.join([f'{key}:{value}' for key, value in result['overallValidationOutcomeByAuthor'].items()])}\n\n")
            else:
                # Files have their own special way of showing up
                files = []
                file_content = validation_result.get('expectedResults', {}).get('FileContent')
                for file in file_content:
                    files.append(file.get('entityUuid'))
                for uuid in files:
                    file_content = self._get(f"{self.root_url}files/{uuid}").json()
                    write_to.write(f"{index + 1} - For submittable with alias {file_content['filename']}, validation results are as following:\n"
                          f"\t\t{newline_tab.join([f'{key}:{value}' for key, value in validation_result['overallValidationOutcomeByAuthor'].items()])}\n\n")

        # If writing to a log, close the file.
        if sys.stdout != write_to:
            write_to.close()

        return validation_results

    def show_validation_errors(self) -> dict:
        if not self._check_submission_availability() and not self._check_submission_blockers():
            print("Submission has no validation errors.")
            return None
        else:
            print("Submission is either completed or has validation errors")
        # TODO add show_validation_errors
        i = 1
        # TODO add show_submission_summary

    def finish_submission(self) -> any((rq.Response, None)):
        """
        Finish a submission. Submissions can only be finished if it isn't finished and there's no blocker.
        :returns response or None : requests.Response or None
                                    Response to the creation or None if submission can't be finished.
        """
        # Only be able to finish submission on uncompleted submissions
        if not self._check_submission_availability():
            return None

        # Only be able to finish submission if there are no blockers
        if self._check_submission_blockers():
            print("Submission has blockers. Please revise that all your submittables have passed validation.")
            return None

        # Change status to "submitted"
        url_to_submit = self.submission.get('_links', {}).get('submissionStatus', {}).get('href')
        response = self._put(url_to_submit, data='{"status" : "Submitted"}')
        self._update_submission()

        # If successful, print it to the user
        if response.status_code < 210:
            print("Submission successfuly finished!")

        return response

    def submit_directory(self, directory: str) -> dict:
        """
        Submit a directory containing JSON files for a submission
        :param directory : str
                           Path to the directory
        :returns self.submission_content.get('_links) : dict
                                                        links to check on the submission contents by
        """
        # Check for directory
        if not os.path.exists(directory):
            print("The provided directory doesn't exist")
        # Walk the directory searching for JSON files
        for (dirpath, dirnames, filenames) in os.walk(directory):
            files = filenames
            break
        files = [f"{directory}/{file}" for file in files if file.endswith('.json')]

        # Parse files. Beware if submission type is not the intended
        for file in files:
            submittable_type = file.split('/')[-1].split('__')[0]
            with open(file, "r") as f:
                submittable = js.loads(f.read())
            self.create_submittable(submittable_type, submittable)

        return self.submission_content.get('_links', None)

    def show_processing_statuses(self):
        """
        Show all the available processing statuses for a submission.
        :returns self.processing_status: list
                                         List with all the processing statuses
        """
        # TODO retrieve paginated processing statuses
        if self._check_submission_availability():
            print("Submission is not finished")
            return None
        self._retrieve_processing_statuses()

        print(f"For submission with ID {self.submission.get('id')}, processing statuses are:\n")
        for status in self.processing_status['_embedded']['processingStatuses']:
            print(f"{status['submittableType']}: alias {status['alias']}:")
            print(f"\tStatus: {status['status']}")
            print(f"\tArchive: {status['archive']}")
            print(f"\tAccession: {status.get('accession')}\n")

        return self.processing_status

    def _set_client(self):
        """
        Set client based on the API root path 'tus-upload'
        :return:
        """
        self.client = client.TusClient(url=self.root.get('tus-upload', {}).get('href'))

    def upload_file(self, path_to_file: str, chunk_size: int = 1024000) -> None:
        """
        Upload a file to the DSP.
        :param path_to_file : str
                              Path to the file
        :param chunk_size : int
                            Chunk size in bytes. Defaults to 10 MB
        :returns None : None
        """
        if not self._check_submission_availability():
            print("This submission is completed")
            return None

        self._set_client()

        print(f"Uploading file {path_to_file.strip().split('/')[-1]}...")
        try:
            uploader = self.client.uploader(file_path=path_to_file, chunk_size=chunk_size,
                                            metadata={'name': path_to_file.strip().split('/')[-1],
                                                      'submissionID': self.submission.get('id'),
                                                      'jwtToken': self.token})
            for _ in tqdm(range(0, uploader.file_size, chunk_size)):
                uploader.upload_chunk()
        except:
            print(f"Seems like this file is giving an error. This might be due to the file being resumed from an"
                  f"upload. Trying to resume upload for file {path_to_file.strip().split('/')[-1]}")
            self.resume_file(path_to_file, chunk_size)



    def resume_file(self, path_to_file: str, chunk_size: int = 1024000) -> None:
        """
        Resume file upload
        :param path_to_file : str
                              path to the file
        :param chunk_size : int
                            Chunk size in bytes. Defaults to 10 MB
        :returns None : None
        """
        if not self._check_submission_availability():
            print("This submission is completed")
            return None

        files = self._retrieve_files()
        filename = path_to_file.strip().split('/')[-1]
        file_content = self._retrieve_submittable_same_alias(files, filename, 'filename')
        print(f"{self.root.get('tus-upload', {}).get('href')}{file_content.get('generatedTusId')}")
        self._set_client()
        self.client.set_headers({'Authorization': f'Bearer {self.token}'})

        print(f"Resuming file upload of {path_to_file.strip().split('/')[-1]}...")
        uploader = self.client.uploader(file_path=path_to_file, chunk_size=chunk_size, url=f"{self.root.get('tus-upload', {}).get('href')}{file_content.get('generatedTusId')}")
        offset = uploader.get_offset()
        for _ in tqdm(range(offset, uploader.file_size, chunk_size), position=0, leave=True):
            uploader.upload_chunk()

    def delete_file(self, filename: str) -> rq.Response:
        """
        Delete a file. Can't delete files that are being uploaded.
        :param filename : Filename of the file that you want to re-upload
        :return:
        """
        if not self._check_submission_availability():
            print("This submission is completed, files can't be deleted")
            return None

        files = self._retrieve_files()
        file_content = self._retrieve_submittable_same_alias(files, filename, 'filename')
        delete_file_url = file_content.get('_links', {}).get('self', {}).get('href')
        response = self._delete(delete_file_url)

        if response.status_code == 204:
            print("Successfully deleted file")

        return response
