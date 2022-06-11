// AWS CDK
import { App, Stack, StackProps } from 'aws-cdk-lib';

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
  }
}

const app = new App();
new SlackReminderStack(app, 'SlackReminder', {
  env: { region: process.env.AWS_REGION },
});
