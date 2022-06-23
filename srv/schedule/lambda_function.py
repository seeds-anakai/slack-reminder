import boto3
import datetime
import dateutil.parser
import dateutil.rrule
import json
import operator
import os
import re
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

    # すべての予定を取得する
    with urllib.request.urlopen(settings['taskCalendarUrl']) as response:
        events = Calendar.parse(response.read().decode())

    # 本日分の予定を抽出する
    tasks = events.between(
        datetime.datetime.now().replace(hour=00, minute=10, second=00, microsecond=000000),
        datetime.datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999),
    )

    # すべての祝日を取得する
    with urllib.request.urlopen(settings['holidayCalendarUrl']) as response:
        events = Calendar.parse(response.read().decode())

    # 本日分の祝日を抽出する
    holidays = events.between(
        datetime.datetime.now().replace(hour=00, minute=00, second=00, microsecond=000000),
        datetime.datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999),
    )

    with table.batch_writer(overwrite_by_pkeys=['Id']) as batch:
        # 本日分の予定を登録する
        for task in tasks:
            batch.put_item(
                Item={
                    'Id': task['UID'],
                    'Date': task['DTSTART'].strftime('%Y-%m-%d'),
                    'Time': task['DTSTART'].strftime('%H:%M:%S'),
                    'ExpiredAt': int(task['DTEND'].timestamp()),
                    'Summary': task['SUMMARY'],
                    'Type': 'TASK',
                },
            )

        # 本日分の祝日を登録する
        for holiday in holidays:
            batch.put_item(
                Item={
                    'Id': holiday['UID'],
                    'Date': holiday['DTSTART'].strftime('%Y-%m-%d'),
                    'Time': holiday['DTSTART'].strftime('%H:%M:%S'),
                    'ExpiredAt': int(holiday['DTEND'].timestamp()),
                    'Summary': holiday['SUMMARY'],
                    'Type': 'HOLIDAY',
                },
            )

class Calendar:
    def __init__(self, events):
        self._events = events

    @classmethod
    def parse(cls, components):
        events = []

        for component in re.split(r'\r\n(?![ \t])', components):
            # 開始
            if component == 'BEGIN:VEVENT':
                params = {}
                continue

            # 開始を通過済みの場合のみ処理を続行する
            if 'params' not in locals():
                continue

            # 日時
            if match := re.fullmatch(r'(DTSTART|DTEND|EXDATE)(?:;TZID=.*|;VALUE=DATE)?:(\d{8}(?:T\d{6}Z?)?)', component):
                params[match[1]] = params.get(match[1], []) + [dateutil.parser.parse(match[2])]
                continue

            # プレーンテキスト
            if match := re.fullmatch(r'(UID|RRULE|SUMMARY|DESCRIPTION):(.*)', component, re.S):
                params[match[1]] = params.get(match[1], []) + [cls.unescape(match[2])]
                continue

            # 終了
            if component == 'END:VEVENT':
                events += [Event(params)]
                del params

        return cls(events)

    @classmethod
    def unescape(cls, component):
        component = component.replace(r'\N', '\n')
        component = component.replace(r'\n', '\n')
        component = component.replace(r'\,', ',')
        component = component.replace(r'\;', ';')
        component = component.replace(r'\\', '\\')
        return re.sub(r'\r\n[ \t]', '', component)

    def between(self, after, before):
        events = []

        for event in self._events:
            # 繰り返しルールが存在する場合
            if event.rrule:
                # 繰り返しルールを解析する
                rules = dateutil.rrule.rrulestr(event.rrule, dtstart=event.dtstart, forceset=True, ignoretz=True)

                # 除外対象の日時を指定する
                for exdate in event.exdate:
                    rules.exdate(exdate)

                # 指定範囲の予定を抽出する
                for start in rules.between(after, before, True):
                    end = start + (event.dtend - event.dtstart)

                    events.append({
                        'UID': event.uid,
                        'DTSTART': start.astimezone(None),
                        'DTEND': end.astimezone(None),
                        'SUMMARY': event.summary,
                    })
                continue

            # 指定範囲の予定を抽出する
            if after <= event.dtstart.astimezone(None).replace(tzinfo=None) <= before:
                events.append({
                    'UID': event.uid,
                    'DTSTART': event.dtstart.astimezone(None),
                    'DTEND': event.dtend.astimezone(None),
                    'SUMMARY': event.summary,
                })

        # 指定範囲の予定を開始時刻で並べ替えて返却する
        return sorted(events, key=operator.itemgetter('DTSTART'))

class Event:
    def __init__(self, params):
        self._params = params

    def __getattr__(self, name):
        if name in ('uid', 'dtstart', 'dtend', 'rrule', 'summary', 'description'):
            return next(iter(self._params.get(name.upper(), [])), None)

        if name in ('exdate',):
            return self._params.get(name.upper(), [])

        raise AttributeError("'{}' object has no attribute '{}'".format(
            self.__class__.__name__,
            name,
        ))
