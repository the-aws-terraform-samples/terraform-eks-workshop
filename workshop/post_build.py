import boto3
from boto3.dynamodb.conditions import Key, Attr
import json
import os
import sys
import toml
import logging
import datetime
import base64
import requests
from requests_aws4auth import AWS4Auth
from botocore.utils import ContainerMetadataFetcher
logger = logging.getLogger()
logger.setLevel(logging.INFO)


# DOES: Analize language used in the content, then update structure of content.

def main():
    # Setup environment
    region = os.environ['RT_REGION']
    workshop_name = os.environ['WORKSHOP_NAME']
    version_table_name = os.environ['VERSION_TABLE']
    dynamodb = boto3.resource('dynamodb')
    #version_table = dynamodb.Table(version_table_name)
    gql_endpoint = os.environ['GQL_ENDPOINT']
    # for now content handle only workshop, in future will be added delivery 
    content_id = workshop_name
    content_structures = []


    # Analize languages in toml file
    dict_toml = toml.load(open('./config.toml'))
    number_of_languages = len(dict_toml['Languages']) - 1
    for i,lang in enumerate(dict_toml['Languages']):
        print('Load JSON structure\n')
        with open("./public/" + lang +"/index.json", 'r') as j:
            current_structure = json.load(j)
        print('Finished Load JSON\n')
        content_structures.append({"language": lang, "structure": current_structure})


    # Change json format from Python to Javascript because GraphQL can only recognize Javascript type of Json object.
    # Javascript Json object {key: "value"} ; Python Json object {"key":"value"}
    # TODO: Json_keys is just hardcoded. It should find keys in JSON object.
    json_keys = ["language", "structure", "pageTitle", "relativePagePath"]
    structures_str = str(content_structures)
    for key in json_keys:
        target_key = "\'"+key+"\'"
        structures_str = structures_str.replace(target_key, key)
    structures_str = structures_str.replace("\'", "\"")

    # Setting Sigv4
    uri = os.environ.get('AWS_CONTAINER_CREDENTIALS_RELATIVE_URI')
    credential = ContainerMetadataFetcher().retrieve_uri(uri)
    access_key_id = credential.get('AccessKeyId')
    secret_access_key = credential.get('SecretAccessKey')
    session_token = credential.get('Token')
    auth = AWS4Auth(access_key_id, secret_access_key, region, 'appsync', session_token=session_token)

    # Load latest version
    body = {"query":""""
                    query ListContentMetaDatas{	
                    listContentMetaDatas(
                            contentId: "%s",
                            limit: 1,
                            sortDirection: DESC
                    ) {
                            items{
                        contentId
                        version
                        }
                    } 
                    }
                    """%workshop_name
            }
            
    body_json = json.dumps(body)
    method = 'POST'
    headers = {}
    response = requests.request(method, gql_endpoint, auth=auth, data=body_json, headers=headers)
    gql_data = json.loads(response.content.decode('utf-8'))['data']['listContentMetaDatas']['items'][0]
    current_version = gql_data['version']
    
    # Send latest version
    body = {"query":""""
            mutation createContentRecord{
            createContentMetaData(input:{
                contentId: "%s"
                version: %d
                workshopName: "%s",
                structures: %s
            }){
                version
            }
            }
            """% (content_id, current_version,workshop_name,structures_str)
    }
    body_json = json.dumps(body)
    response = requests.request(method, gql_endpoint, auth=auth, data=body_json, headers=headers)


    # # Send structure data to DynamoDB Table
    # print('Start to send structure data\n')
    # query_response = version_table.query(
    #     KeyConditionExpression=Key('content_id').eq(content_id),
    #     ScanIndexForward = False,
    #     Limit = 1 
    #     )
    # # Current version is already updated in pre_build.py 
    # current_version = int(query_response['Items'][0]['version'])
    # unix_timestamp = datetime.datetime.now().strftime('%s')
    # update_response = version_table.update_item(
    #         Key = 
    #         {
    #             'content_id': content_id,
    #             'version' : current_version
    #         },
    #         UpdateExpression='SET updated_at = :val1, structure = :val2',
    #         ExpressionAttributeValues={
    #             ':val1': unix_timestamp,
    #             ':val2': structure_json
    #         }
    #     )
    print('Finished sending sructure\n')

    print('Post build phase done\n')

if __name__ == "__main__":
    debug = False
    if debug:
        logger.setLevel(logging.DEBUG)
        os.environ['WORKSHOP_NAME'] = 'your_content_id'
        os.environ['VERSION_TABLE'] = 'test_content_meta_table'
            
    main()
