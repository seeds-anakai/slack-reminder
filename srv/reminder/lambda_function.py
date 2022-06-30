import boto3
import datetime
import json
import os
import urllib.request

# DynamoDB
dynamodb = boto3.resource('dynamodb')

# DynamoDB - Event Table
table = dynamodb.Table(os.environ['EVENT_TABLE_NAME'])

# Systems Manager
ssm = boto3.client('ssm')

def lambda_handler(event, context):
    # 設定のJSONを取得する
    response = ssm.get_parameter(Name=os.environ['SETTING_PARAMETER_NAME'])

    # 設定のJSONをデコードする
    settings = json.loads(response['Parameter']['Value'])

    # 現在の日時を取得する
    now = datetime.datetime.now()

    # 本日の予定を取得する
    response = table.query(
        IndexName='GSI-DateTime',
        KeyConditions={
            'Date': {
                'AttributeValueList': [
                    f'{now:%Y-%m-%d}',
                ],
                'ComparisonOperator': 'EQ',
            },
        },
    )

    # 本日が祝日の場合は処理を中断する
    if any(item['Type'] == 'HOLIDAY' for item in response['Items']):
        return

    # 5分後の日時を算出する
    after_5_minutes = now + datetime.timedelta(minutes=5)

    # 5分後の予定を抽出する
    tasks = [item for item in response['Items'] if item['Type'] == 'TASK' and item['Time'] == f'{after_5_minutes:%H:%M:00}']

    # 5分後の予定が存在しない場合は処理を中断する
    if not tasks:
        return

    # 5分後の予定を整形する
    data = {
        'text': os.linesep.join(['<!channel>'] + ['【5分前】' + task['Summary'] for task in tasks]),
    }

    # 5分後の予定を通知する
    with urllib.request.urlopen(urllib.request.Request(settings['slackWebhookUrl'], json.dumps(data).encode())) as response:
        print(response.read().decode())
