# CryoSPARC Job Watcher (cs_watch.py)

A lightweight script to monitor CryoSPARC jobs and send notifications
when jobs **complete**, **fail**, or are **killed**. Used Pushover or Slack to handle notifications.

------------------------------------------------------------------------

## Installation (dependencies)

In your CS Tools environment:

``` bash
pip install cryosparc-tools requests
```

------------------------------------------------------------------------

## Basic Usage

### Monitor a single job

``` bash
python3 cs_watch.py P40 J272 --slack-webhook URL
```

### Monitor all active jobs in a workspace

``` bash
python3 cs_watch.py P40 W1 --all-active --slack-webhook URL
```

### Using Pushover

``` bash
python3 cs_watch.py P40 J272   --pushover-token TOKEN   --pushover-user USER_KEY
```

------------------------------------------------------------------------

## Slack Setup

1.  Go to https://api.slack.com/apps
2.  Click **Create New App**
3.  Enable **Incoming Webhooks**
4.  Click **Add New Webhook to Workspace**
5.  Choose a channel (recommend a **private channel**)
6.  Copy the webhook URL

Run:

``` bash
python3 cs_watch.py P40 W1 --all-active   --slack-webhook "https://hooks.slack.com/services/XXX/YYY/ZZZ"
```

### Notes

-   Use a **private channel** if you only want notifications for
    yourself
-   Slack messages are formatted with job details and status

------------------------------------------------------------------------

## Pushover Setup (Best for phone alerts)

1.  Create account: https://pushover.net
2.  Create application: https://pushover.net/apps/build
3.  Copy:
    -   **API Token/Key**
    -   **User Key**

Run:

``` bash
python3 cs_watch.py P40 J272   --pushover-token YOUR_API_TOKEN   --pushover-user YOUR_USER_KEY
```

------------------------------------------------------------------------

## Example Notification

    CS 2D classification job "Initial cleanup" P40 W1 J272 (Particles) has completed

Slack version includes: - status emoji - structured formatting

------------------------------------------------------------------------

## Notes

-   Requires access to CryoSPARC via `~/instance_info.json`
-   Works best when run on CryoSPARC master node
-   Notifications only trigger on **state transitions after script
    start**
