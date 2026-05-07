#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Optional

import requests


TERMINAL_STATUSES = {"completed", "failed", "killed"}


def connect_cryosparc(instance_info_path: str):
    from cryosparc.tools import CryoSPARC

    path = Path(instance_info_path).expanduser()
    if not path.exists():
        raise RuntimeError(f"Missing instance_info.json at {path}")

    data = json.loads(path.read_text())
    cs = CryoSPARC(**data)

    if not cs.test_connection():
        raise RuntimeError("Failed to connect to CryoSPARC")

    return cs


def object_to_dict(obj: Any) -> dict:
    if obj is None:
        return {}

    if isinstance(obj, dict):
        return obj

    for method in ("model_dump", "dict", "to_dict"):
        if hasattr(obj, method):
            try:
                return getattr(obj, method)()
            except Exception:
                pass

    return {}


def get_field(obj: Any, *names: str, default: Optional[Any] = None):
    containers = [
        obj,
        object_to_dict(getattr(obj, "model", None)),
        object_to_dict(getattr(obj, "doc", None)),
        object_to_dict(obj),
    ]

    for name in names:
        for container in containers:
            if isinstance(container, dict):
                val = container.get(name)
            else:
                val = getattr(container, name, None)

            if val not in (None, ""):
                return val

    return default


def human_status(status: str) -> str:
    return {
        "completed": "has completed",
        "failed": "has failed",
        "killed": "has been killed",
    }.get(status, f"has {status}")


def status_emoji(status: str) -> str:
    return {
        "completed": "✅",
        "failed": "❌",
        "killed": "🛑",
    }.get(status, "ℹ️")


def human_job_type(cs: Any, raw_type: str) -> str:
    try:
        spec = cs.job_register.get(raw_type)

        for attr in ("title", "name", "label", "display_name"):
            val = getattr(spec, attr, None)
            if val:
                return str(val).strip().lower()

        spec_dict = object_to_dict(spec)
        for key in ("title", "name", "label", "display_name"):
            val = spec_dict.get(key)
            if val:
                return str(val).strip().lower()

    except Exception:
        pass

    return raw_type.replace("_", " ")


def get_workspace_title(cs: Any, project_uid: str, workspace_uid: str) -> str:
    if not workspace_uid or workspace_uid == "W?":
        return "unknown workspace"

    try:
        ws = cs.find_workspace(project_uid, workspace_uid)
        return str(
            get_field(
                ws,
                "title",
                "name",
                "desc",
                "description",
                default="unknown workspace",
            )
        )
    except Exception:
        return "unknown workspace"


def get_job_info(
    cs: Any,
    job: Any,
    fallback_project: Optional[str] = None,
    fallback_workspace: Optional[str] = None,
) -> dict:
    project = str(get_field(job, "project_uid", default=fallback_project or "P?"))

    workspace = str(
        get_field(
            job,
            "workspace_uid",
            "workspace",
            default=fallback_workspace or "W?",
        )
    )

    job_uid = str(get_field(job, "uid", "job_uid", default="J?"))

    raw_type = str(get_field(job, "type", "job_type", default="unknown_job_type"))
    job_type = human_job_type(cs, raw_type)

    job_title = str(
        get_field(job, "title", "job_title", "name", default="untitled job")
    )

    workspace_title = get_workspace_title(cs, project, workspace)

    status_raw = str(job.status)
    status_text = human_status(status_raw)

    return {
        "project": project,
        "workspace": workspace,
        "workspace_title": workspace_title,
        "job_uid": job_uid,
        "job_type": job_type,
        "job_title": job_title,
        "status_raw": status_raw,
        "status_text": status_text,
        "emoji": status_emoji(status_raw),
    }


def plain_message(info: dict) -> str:
    return (
        f'CS {info["job_type"]} job "{info["job_title"]}" '
        f'{info["project"]} {info["workspace"]} {info["job_uid"]} '
        f'({info["workspace_title"]}) {info["status_text"]}'
    )


def slack_message(info: dict) -> dict:
    title = f'{info["emoji"]} CryoSPARC job {info["status_text"]}'

    text = (
        f'*{title}*\n'
        f'*Project:* `{info["project"]}`\n'
        f'*Workspace:* `{info["workspace"]}` — {info["workspace_title"]}\n'
        f'*Job:* `{info["job_uid"]}` — {info["job_type"]}\n'
        f'*Title:* "{info["job_title"]}"'
    )

    return {"text": text}


def notify_pushover(token: str, user: str, message: str):
    r = requests.post(
        "https://api.pushover.net/1/messages.json",
        data={"token": token, "user": user, "message": message},
        timeout=10,
    )
    if not r.ok:
        raise RuntimeError(f"Pushover failed: {r.status_code}\n{r.text}")


def notify_slack(webhook_url: str, payload: dict):
    r = requests.post(webhook_url, json=payload, timeout=10)
    if not r.ok:
        raise RuntimeError(f"Slack failed: {r.status_code}\n{r.text}")


def find_jobs(cs: Any, project_uid: str, workspace_uid: Optional[str] = None):
    if workspace_uid:
        return list(cs.find_jobs(project_uid, workspace_uid))
    return list(cs.find_jobs(project_uid))


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("project_uid")
    parser.add_argument("arg2", nargs="?")
    parser.add_argument("arg3", nargs="?")

    parser.add_argument("--workspace")
    parser.add_argument("--job")
    parser.add_argument("--all-active", action="store_true")
    parser.add_argument("--interval", type=int, default=60)

    parser.add_argument("--instance-info", default="~/instance_info.json")

    parser.add_argument("--pushover-token")
    parser.add_argument("--pushover-user")
    parser.add_argument("--slack-webhook")

    args = parser.parse_args()

    use_pushover = bool(args.pushover_token and args.pushover_user)
    use_slack = bool(args.slack_webhook)

    if not use_pushover and not use_slack:
        raise SystemExit("Provide --slack-webhook or both --pushover-token and --pushover-user")

    project = args.project_uid
    workspace = args.workspace
    job = args.job

    if args.arg2:
        if args.arg2.upper().startswith("W"):
            workspace = args.arg2
        elif args.arg2.upper().startswith("J"):
            job = args.arg2

    if args.arg3:
        job = args.arg3

    if not job and not args.all_active:
        raise SystemExit("Specify a job UID or use --all-active")

    cs = connect_cryosparc(args.instance_info)

    notified = set()
    first_scan = True

    while True:
        if job:
            jobs = [cs.find_job(project, job)]
        else:
            jobs = find_jobs(cs, project, workspace)

        for j in jobs:
            j.refresh()

            jid = str(get_field(j, "uid", "job_uid", default=""))
            if not jid:
                continue

            this_project = str(get_field(j, "project_uid", default=project))
            key = f"{this_project}/{jid}"
            status = str(j.status)

            if args.all_active and first_scan and status in TERMINAL_STATUSES:
                notified.add(key)
                continue

            if status in TERMINAL_STATUSES and key not in notified:
                info = get_job_info(
                    cs,
                    j,
                    fallback_project=project,
                    fallback_workspace=workspace,
                )

                if use_pushover:
                    notify_pushover(
                        args.pushover_token,
                        args.pushover_user,
                        plain_message(info),
                    )

                if use_slack:
                    notify_slack(args.slack_webhook, slack_message(info))

                notified.add(key)

        first_scan = False

        if job and notified:
            break

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
