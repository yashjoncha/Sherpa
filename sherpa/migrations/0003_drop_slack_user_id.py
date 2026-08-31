"""Drop the Slack user mapping along with the Slack and tracker integrations."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("sherpa", "0002_auto_register_nullable_slack"),
    ]

    operations = [
        migrations.RemoveField(model_name="member", name="slack_user_id"),
        migrations.AlterModelOptions(
            name="member",
            options={"ordering": ["display_name"]},
        ),
    ]
