import requests as rq
import json as js
from datetime import datetime
import os

#TODO change name afterwards

hca_to_biostudies = {'project_short_name': 'alias',
                     'project_title': 'title',
                     'project_description': 'description',
                     'name': 'firstName',
                     'orcid_id': 'orcid',
                     'project_role': 'roles',
                     'email': 'email',
                     'institution': 'affiliation',
                     'phone': 'phone',
                     'address': 'address'
                     }

hca_to_biosamples = {'biomaterial_core - biomaterial_id': 'alias',
                     'biomaterial_core - biomaterial_name': 'name',
                     'biomaterial_core - biomaterial_description': 'description',
                     'biomaterial_core - ncbi_taxon_id': 'taxonId',
                     'genus_species - ontology_label' : 'taxon'}

grant_conversion = {'grant_title': 'grantTitle',
                    'grant_id': 'grantId',
                    'organization': 'organization'}


publication_conversion = {
    'authors': 'authors',
    'doi': 'doi',
    'title': 'articleTitle',
    'pmid': 'pubmedId',

}

#TODO add a more complete list
role_conversion = {'data curator': 'curator',
                   'experimental scientist': 'experiment performer',
                   'computational scientist': 'data analyst',
                   'principal investigator': 'investigator',
                   'biomaterial provider': 'biomaterial provider'}

def unpack_dictionary(in_dict, out_dict={}, nested_key = ""):
    for key, value in in_dict.items():
        if any(key == s for s in ["schema_type", "describedBy"]):
            continue
        if isinstance(value, dict):
            out_dict = unpack_dictionary(value, out_dict, "{}{}{}".format(nested_key, " - " if nested_key else "", key))
        elif isinstance(value, list):
            if isinstance(value[0], dict):
                for dictionary in value:
                    out_dict = unpack_dictionary(dictionary, out_dict, "{}{}{}".format(nested_key, " - " if nested_key else "", key))
            else:
                out_dict["{}{}{}".format(nested_key, " - " if nested_key else "", key)] = str(value)
        else:
            out_dict[nested_key + (" - " if nested_key else "") + key] = value
    return out_dict



def correct_sample_metadata(sample_dict):
    attributes_to_delete = []
    attributes_to_change = {}
    for name, attribute in sample_dict['attributes'].items():
        fq_minus_end = " - ".join(name.split(" - ")[:-1])
        last_key = name.split(" - ")[-1]
        if any([last_key in s for s in ['ontology', 'text', 'ontology_label']]):
            attributes_to_delete.append(name)
            if fq_minus_end not in attributes_to_change:
                attributes_to_change[fq_minus_end] = {last_key: attribute}
            else:
                if last_key not in attributes_to_change[fq_minus_end]:
                    attributes_to_change[fq_minus_end][last_key] = []
                attributes_to_change[fq_minus_end][last_key].extend(attribute)

    # Add ontologies
    for ontologised_term, value in attributes_to_change.items():
        for i in range(len(value['ontology'])):
            ols_response = rq.get(f"https://www.ebi.ac.uk/ols/api/terms/findByIdAndIsDefiningOntology?id={value['ontology'][i]['value']}").json()
            if '_embedded' not in ols_response:
                print(f"Couldn't find the term for {value['ontology'][i]['value']}. The ols response is:\n{ols_response}")
                continue
            for term in ols_response['_embedded']['terms']:
                if not term['is_defining_ontology']:
                    continue
                else:
                    if len(value['ontology']) > 1:
                        index_str = f'_{i + 1}'
                    else:
                        index_str = ''
                    sample_dict['attributes'][f"{ontologised_term}{index_str}"] = []
                    sample_dict['attributes'][f"{ontologised_term}{index_str}"].append({'value': term['label']})
                    sample_dict['attributes'][f"{ontologised_term}{index_str}"][-1]['terms'] = [{'url': ols_response['_embedded']['terms'][0]['iri']}]
                    break
            else:
                print(f"Couldn't find a defining ontology for {value['ontology'][0]['value']}")
                sample_dict['attributes'][ontologised_term] = [{}]
                sample_dict['attributes'][ontologised_term][0]['value'] = value['label'][0]['value']

    # Search for units
    for attribute, value in sample_dict['attributes'].items():
        if "unit" in attribute:
            name_to_search = attribute.replace("_unit", "")
            for attribute2, value2 in sample_dict['attributes'].items():
                if name_to_search == attribute2:
                    for sub_value in value:
                        sub_value['units'] = sub_value['value']
                        sub_value['value'] = value2[0]['value']
                    attributes_to_delete.append(attribute)
                    sample_dict['attributes'][attribute2] = value
                    break

    for attribute in attributes_to_delete:
        del sample_dict['attributes'][attribute]
    return sample_dict

#Hacky function to correct some metadata about contributors
def correct_contributor_metadata(project_dict):
    for contact in project_dict['contacts']:
        firstName,middleInitials, lastName = contact['firstName'].split(",")
        contact['firstName'] = firstName
        contact['middleInitials'] = middleInitials
        contact['lastName'] = lastName

        if 'project_role.ontology_label' in contact['attributes']:
            contact['roles'] = []
            contact['roles'].append(role_conversion[contact['attributes']['project_role.ontology_label'][0]['value']])
            del contact['attributes']['project_role.ontology_label']
            del contact['attributes']['project_role.ontology']
            del contact['attributes']['project_role.text']

    return project_dict

# TODO Change to resemble get_sample_information (Unpacked values too late, need to also change mapping)
def get_project_information(entity):
    project = {}
    project['attributes'] = {}
    project['contacts'] = []
    project['fundings'] = []
    for content, value in entity.content.items():
        if isinstance(value, dict):
            for sub_content, sub_value in unpack_dictionary(value, {}).items():
                if sub_content in hca_to_biostudies:
                    project[hca_to_biostudies[sub_content]] = sub_value
                else:
                    project['attributes'][sub_content] = [{'value': sub_value}]

        if "contributors" in content:
            contributor_index = 0
            for contributor in value:
                contributor_info = unpack_dictionary(contributor, {})
                project['contacts'].append({})
                project['contacts'][contributor_index]['attributes'] = {}
                for contributor_field, contributor_value in contributor_info.items():
                    if contributor_field in hca_to_biostudies:
                        project['contacts'][contributor_index][hca_to_biostudies[contributor_field]] = contributor_value
                    else:
                        # Can't add additional properties to contacts
                        continue
                contributor_index += 1

        elif "funders" in content:
            for funder in value:
                project_funding = unpack_dictionary(funder, {})
                funding = {}
                for key_name, funding_value in project_funding.items():
                    funding[grant_conversion[key_name]] = funding_value
                project['fundings'].append(funding)

        elif 'publications' in content:
            # TODO for when not time restriction
            continue

        elif not any(content in banned_properties for banned_properties in ['describedBy', 'schema_type']):
            # TODO for when no time restriction
            continue

    project = correct_contributor_metadata(project)
    project['releaseDate'] = datetime.now().strftime("%Y-%m-%d")
    return project

def get_sample_information(entity):
    sample = {}
    sample['attributes'] = {}
    sample['releaseDate'] = datetime.now().strftime("%Y-%m-%d")
    for sample_field, sample_value in unpack_dictionary(entity.content, {}).items():
        if sample_field == 'genus_species - ontology' or sample_field == 'genus_species - text':
            continue
        if sample_field in hca_to_biosamples:
            if sample_field == 'biomaterial_core - ncbi_taxon_id':
                sample_value = 9606
            sample[hca_to_biosamples[sample_field]] = sample_value
        else:
            if isinstance(sample_value, str):
                sample_value = sample_value.split('||')
                sample['attributes'][sample_field] = []
                for value in sample_value:
                    sample['attributes'][sample_field].append({'value': value})
            else:
                sample['attributes'][sample_field] = [{'value': sample_value}]
    sample['attributes']['Biomaterial type'] = [{'value': entity.concrete_type}]
    sample = correct_sample_metadata(sample)

    # Bit to add relationship linking
    sample['sampleRelationships'] = []
    for entity_name, id in entity.links_by_entity.items():
        if entity_name == 'biomaterial':
            #TODO add case when more than one id linked (?)
            sample['sampleRelationships'].append({"alias": id[0],
                                                  "relationshipNature": "derived from"})
        if entity_name == 'protocol':
            sample['attributes']['protocolsToAdd'] = id
    if not sample['sampleRelationships']:
        del sample['sampleRelationships']

    return sample

def get_study_information(entity):
    study = {}
    study['alias'] = entity.content['project_core']['project_short_name']
    study['title'] = entity.content['project_core']['project_title']
    study['projectRef'] = {'alias': study['alias']}
    study['attributes'] = {}
    study['attributes']['study_abstract'] = [{'value': entity.content['project_core']['project_description']}]
    study['attributes']['study_type'] = [{'value': 'RNASeq'}]
    #TODO investigate how to do this automatically. For now it will copy projects
    return study

# TODO Check how we will cope with experiments having more than 1 sequencing/library prep protocol
# TODO Automatically assign methods
# TODO Assign different assays for different samples
def get_assay_information(entity_lib, entity_seq, files):
    assay = {}
    description = ''
    assay['alias'] = f"{entity_lib.id}_{entity_seq.id}"
    if 'protocol_description' in entity_lib.content['protocol_core']:
        description += f"{entity_lib.content['protocol_core']['protocol_description']}\n"
    if 'protocol_description' in entity_seq.content['protocol_core']:
        description += f"{entity_lib.content['protocol_core']['protocol_description']}\n"
    assay['description'] = description
    combined_entities = unpack_dictionary({**entity_lib.content, **entity_seq.content}, {})

    assay['sampleUses'] = []

    #TODO map ontologies we use to library strategies enum from dsp
    assay['attributes'] = {}
    assay['attributes']['library_strategy'] = [{'value': 'RNA-Seq' if 'RNA sequencing' in combined_entities['method - ontology_label'] else ''}]
    assay['attributes']['library_source'] = [{'value': 'TRANSCRIPTOMIC SINGLE CELL'}]
    assay['attributes']['library_selection'] = [{'value': 'Oligo-dT' if combined_entities['assay'] == 'poly-dT' else ''}]
    assay['attributes']['library_layout'] = [{'value': 'PAIRED' if combined_entities['paired_end'] else 'SINGLE'}]
    #TODO change platform
    assay['attributes']['platform_type'] = [{'value': 'ILLUMINA'}]
    assay['attributes']['instrument_model'] = [{'value': combined_entities['instrument_manufacturer_model - ontology_label']}]
    #TODO add nominal_length and nominal_sdev
    return assay

def get_assay_data_information(files):
    assay_data = {}
    assay_data['alias'] = 0
    return assay_data

def correct_linking(entity_map, samples, project, study,  assays, assay_data):
    for i in range(len(samples)):
        n = 0
    for sample in samples:
        if sample['Biomaterial type'] == 'cell_suspension':
            for assay in assays:
                assay['sampleUses'].append({'sampleRef': {'alias': sample['alias']}})

def add_protocol_information(entity_dict, protocols):
    for sample in entity_dict['samples']:
        if 'protocolsToAdd' in sample['attributes']:
            for protocol_id in sample['attributes']['protocolsToAdd']:
                for key, value in unpack_dictionary(protocols[protocol_id].content, {}).items():
                    if isinstance(value, str):
                        value = value.split("||")
                        sample['attributes'][f"{protocols[protocol_id].concrete_type} - {key}"] = [{'value': sub_value} for sub_value in value]
            sample = correct_sample_metadata(sample)
            del sample['attributes']['protocolsToAdd']
    return entity_dict



def get_json_from_map(entity_map):
    library_prep_entity = ''
    sequencing_entity = ''
    entity_dict = {
        'files': [],
        'samples': [],
        'assays': [],
        'project': [],
        'study': [],
        'sequence_processes': []
                   }
    protocols = {}
    for entity in entity_map:
        if entity.type == "biomaterial":
            entity_dict['samples'].append(get_sample_information(entity))

        if entity.type == "project":
            entity_dict['project'].append(get_project_information(entity))
            entity_dict['study'].append(get_study_information(entity))

        if entity.type == 'protocol':
            protocols[entity.id] = entity
        """
        if entity.concrete_type == 'library_preparation_protocol':
            library_prep_entity = entity
        if entity.concrete_type == 'sequencing_protocol':
            sequencing_entity = entity

        if entity.concrete_type == 'sequence_file':
            entity_dict['files'].append(entity)
        """

    assay_processes = {}
    entity_dict = add_protocol_information(entity_dict, protocols)
    return entity_dict
    for file in entity_dict['files']:
        if file.links_by_entity['process'][0] not in assay_processes:
            assay_processes[file.links_by_entity['process'][0]] = [file.links_by_entity['process'][0]]
        else:
            assay_processes[file.links_by_entity['process'][0]].append(file.links_by_entity['process'][0])
        assay_processes = [file.links_by_entity['process'][0] for file in entity_dict['files']]
    assays = get_assay_information(library_prep_entity, sequencing_entity, process)

    assay_data = get_assay_data_information(files)

def write_json_to_submit(entity_dict='', directory=''):
    if directory:
        if not os.path.exists(directory):
            os.mkdir(directory)
    if not directory.endswith("/"):
        directory += '/'

    for entity_type, list_of_entities in entity_dict.items():
        if list_of_entities:
            for entity in list_of_entities:
                json_in_string = js.dumps(entity)
                with open(f"{directory}{entity_type}_{entity['alias']}.json", 'w') as f:
                    f.write(json_in_string)
