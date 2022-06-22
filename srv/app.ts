// Node.js Core Modules
import path from 'path';

// AWS CDK
import { App, Duration, Stack, StackProps } from 'aws-cdk-lib';

// AWS CDK - DynamoDB
import { AttributeType, Table } from 'aws-cdk-lib/aws-dynamodb';

// AWS CDK - EventBridge
import { Rule, Schedule } from 'aws-cdk-lib/aws-events';

// AWS CDK - EventBridge - Event Targets
import { LambdaFunction } from 'aws-cdk-lib/aws-events-targets';

// AWS CDK - Lambda
import { Code, Function, Runtime } from 'aws-cdk-lib/aws-lambda';

// AWS CDK - Systems Manager
import { StringParameter } from 'aws-cdk-lib/aws-ssm';

// Constructs
import { Construct } from 'constructs';

/**
 * A root construct which represents a single CloudFormation stack.
 */
class SlackReminderStack extends Stack {
  /**
   * Creates a new stack.
   *
   * @param scope Parent of this stack, usually an `App` or a `Stage`, but could be any construct.
   * @param id The construct ID of this stack. If `stackName` is not explicitly
   * defined, this id (and any parent IDs) will be used to determine the
   * physical ID of the stack.
   * @param props Stack properties.
   */
  constructor(scope?: Construct, id?: string, props?: StackProps) {
    super(scope, id, props);

    // Settings
    const settingParameter = new StringParameter(this, 'SettingParameter', {
      stringValue: JSON.stringify({
        taskCalendarUrl: '',
        holidayCalendarUrl: '',
        slackWebhookUrl: '',
      }),
    });

    // Events
    const eventTable = new Table(this, 'EventTable', {
      partitionKey: {
        name: 'Id',
        type: AttributeType.STRING,
      },
      readCapacity: 1,
      writeCapacity: 1,
      timeToLiveAttribute: 'ExpiredAt',
    });

    // Events - The GSI of date and time.
    eventTable.addGlobalSecondaryIndex({
      indexName: 'GSI-DateTime',
      partitionKey: {
        name: 'Date',
        type: AttributeType.STRING,
      },
      sortKey: {
        name: 'Time',
        type: AttributeType.STRING,
      },
      readCapacity: 1,
      writeCapacity: 1,
    });

    // Schedule Function
    const scheduleFunction = new Function(this, 'ScheduleFunction', {
      runtime: Runtime.PYTHON_3_9,
      code: Code.fromAsset(path.join(__dirname, 'schedule')),
      handler: 'lambda_function.lambda_handler',
      timeout: Duration.seconds(90),
      environment: {
        TZ: 'Asia/Tokyo',
      },
    });

    // Schedule Rule
    new Rule(this, 'ScheduleRule', {
      schedule: Schedule.cron({
        minute: '0',
        hour: '15',
        weekDay: 'SUN-THU',
      }),
      targets: [
        new LambdaFunction(scheduleFunction),
      ],
    });

    // Environment Variables
    [['SETTING_PARAMETER_NAME', settingParameter.parameterName], ['EVENT_TABLE_NAME', eventTable.tableName]].forEach(([key, value]) => {
      scheduleFunction.addEnvironment(key, value);
    });

    // Permissions
    [scheduleFunction].forEach((grantee) => {
      settingParameter.grantRead(grantee);
      settingParameter.grantWrite(grantee);
      eventTable.grantFullAccess(grantee);
    });
  }
}

const app = new App();
new SlackReminderStack(app, 'SlackReminder', {
  env: { region: process.env.AWS_REGION },
});
