# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# AWS Ground Station CLI contact scheduling, viewing and cancelation

# The program can:
# 1. Schedule contacts with elevation and duration requirements
# 2. Show contacts
# 3. Cancel scheduled contacts

# It uses your default credentials/region stored in the /.aws folder

# NB: Canceling on demand contacts incurs their full cost!

# boto3 GroundStation reference: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/groundstation.html


import boto3
import datetime
import time
from PyInquirer import prompt, Separator
import regex
from prompt_toolkit.validation import Validator, ValidationError


pass_window_start = ""
pass_window_end = ""


def get_satellite_arn(gs_client, norad_ID):

    satellite_arn = ""

    satellite_list = gs_client.list_satellites()

    for satellite in satellite_list["satellites"]:
        if satellite["noradSatelliteID"] == norad_ID:
            satellite_arn = satellite["satelliteArn"]
            break

    if satellite_arn == "":
        print("Not a valid NORAD ID")

    return satellite_arn


def get_mission_profile_arn(gs_client, profile_name):

    profile_arn = ""

    mission_profile_list = gs_client.list_mission_profiles()

    for profile in mission_profile_list["missionProfileList"]:
        if profile["name"] == profile_name:
            profile_arn = profile["missionProfileArn"]
            break

    if profile_arn == "":
        print("Not a valid profile name")

    return profile_arn


def get_mission_profile_name(gs_client, mission_profile_arn):

    mission_profile_name = ""

    mission_profile_id = mission_profile_arn.split("/")[1]

    response = gs_client.get_mission_profile(missionProfileId=mission_profile_id)

    mission_profile_name = response["name"]

    return mission_profile_name


def get_satellite_list(gs_client):

    satellite_list = []

    responce = gs_client.list_satellites()

    if responce["satellites"]:
        for satellite in responce["satellites"]:
            satellite_list.append(str(satellite["noradSatelliteID"]))
    else:
        print("No onboarded satellites in the region.")
        main()

    satellite_list.append("Exit")
    return satellite_list


def get_mission_profile_list(gs_client):

    mission_profile_list = []

    responce = gs_client.list_mission_profiles()

    mission_profile_list.append(
        Separator("               Name             --   Region      ")
    )

    if responce["missionProfileList"]:
        for profile in responce["missionProfileList"]:
            mission_profile_details = (
                str(profile["name"]).ljust(30) + "  --  " + profile["region"]
            )
            mission_profile_list.append(mission_profile_details)
    else:
        print("No available mission profiles in this region.")
        main()

    mission_profile_list.append("Exit")

    return mission_profile_list


def get_onboarded_ground_stations(gs_client, satellite_id, region):

    onboarded_ground_stations = []

    responce = gs_client.list_ground_stations(satelliteId=satellite_id)
    if responce["groundStationList"]:
        for ground_station in responce["groundStationList"]:
            onboarded_ground_stations.append(
                {"name": ground_station["groundStationName"]}
            )
    else:
        print("No onboarded ground stations for this mission profile.")
        main()

    return onboarded_ground_stations


def get_pass_details(passes):

    pass_times = []

    pass_times.append(
        Separator(
            "       Date   --    Start time    --     End time     --  Max contact duration  --  Ground station  --  Mission Profile Region  --  Max Elevation (deg.)"
        )
    )

    for _pass in passes:

        duration = _pass["endTime"] - _pass["startTime"]

        pass_details = (
            str(_pass["startTime"].astimezone(tz=datetime.timezone.utc).date())
            + "  --  "
            + str(_pass["startTime"].astimezone(tz=datetime.timezone.utc)).split(" ")[1]
            + "  --  "
            + str(_pass["endTime"].astimezone(tz=datetime.timezone.utc)).split(" ")[1]
            + "  --  "
            + str(duration).ljust(20)
            + "  --  "
            + str(_pass["groundStation"]).ljust(14)
            + "  --  "
            + str(_pass["region"]).ljust(22)
            + "  --  "
            + str(_pass["maximumElevation"]["value"])
        )
        pass_times.append({"name": pass_details})

    return pass_times


def get_start_dates(today):

    dates = []

    for day in range(6):

        date = today + datetime.timedelta(days=day)
        dates.append(str(date))

    dates.append("Exit")

    return dates


def get_end_dates(pass_window_start_datetime, day_delta):

    dates = []

    for day in range(day_delta - 1):

        date = (
            pass_window_start_datetime
            + datetime.timedelta(days=1)
            + datetime.timedelta(days=day)
        )
        dates.append(str(date))

    dates.append("Exit")

    return dates


class DateValidator(Validator):
    def validate(self, document):

        ok = regex.match(
            "((18|19|20)[0-9]{2}[\-.](0[13578]|1[02])[\-.](0[1-9]|[12][0-9]|3[01]))|(18|19|20)[0-9]{2}[\-.](0[469]|11)[\-.](0[1-9]|[12][0-9]|30)|(18|19|20)[0-9]{2}[\-.](02)[\-.](0[1-9]|1[0-9]|2[0-8])|(((18|19|20)(04|08|[2468][048]|[13579][26]))|2000)[\-.](02)[\-.]29",
            document.text,
        )
        if not ok:
            raise ValidationError(
                message="Please enter a valid date in the YYYY-MM-DD format",
                cursor_position=len(document.text),
            )


def get_contact_window(direction):

    global pass_window_start
    global pass_window_end

    scheduling_window_days = 6
    today = datetime.date.today()

    if direction == "future":
        scheduling_window_end = today + datetime.timedelta(days=scheduling_window_days)

        scheduling_window_start_date = str(today.strftime("%Y-%m-%d"))

        scheduling_window_end_date = str(scheduling_window_end.strftime("%Y-%m-%d"))

        scheduling_window_end = str(scheduling_window_end)

    if direction == "all":
        scheduling_window_start = today - datetime.timedelta(
            days=scheduling_window_days
        )

        scheduling_window_end = today + datetime.timedelta(days=scheduling_window_days)

        scheduling_window_start_date = str(scheduling_window_start.strftime("%Y-%m-%d"))

        scheduling_window_end_date = str(scheduling_window_end.strftime("%Y-%m-%d"))

    today = str(today)

    pass_window_start_question = [
        {
            "type": "input",
            "name": "pass_window_start",
            "message": "Enter the contact window start [YYYY-MM-DD].",
            "default": scheduling_window_start_date,
            "validate": DateValidator,
        }
    ]

    pass_window_start_answer = prompt(pass_window_start_question)
    pass_window_start = pass_window_start_answer["pass_window_start"]

    if direction == "future":
        if pass_window_start < today:
            print("The start date cannot be in the past. Try again.")
            get_contact_window(direction)

        if pass_window_start > scheduling_window_end:
            print("On demand contacts can only be booked 7 days in advance. Try again.")
            get_contact_window(direction)

    pass_window_end_question = [
        {
            "type": "input",
            "name": "pass_window_end",
            "message": "Enter the contact window end   [YYYY-MM-DD].",
            "default": scheduling_window_end_date,
            "validate": DateValidator,
        }
    ]

    pass_window_end_answer = prompt(pass_window_end_question)
    pass_window_end = pass_window_end_answer["pass_window_end"]

    if pass_window_end <= pass_window_start:
        print("The start date has to be before the end date. Try again.")
        get_contact_window(direction)

    if direction == "future":
        if pass_window_end > scheduling_window_end:
            print("On demand contacts can only be booked 7 days in advance. Try again.")
            get_contact_window(direction)

    return pass_window_start, pass_window_end


def get_contacts(gs_client, contact_type):

    pass_number = 100

    satellite_question = [
        {
            "type": "list",
            "name": "satellite_NORAD_ID",
            "message": "Which satellite would you like to use?",
            "choices": get_satellite_list(gs_client),
        }
    ]

    satellite_answer = prompt(satellite_question)
    if satellite_answer["satellite_NORAD_ID"] == "Exit":
        print("No satellite selected. Exiting to main menu.")
        main()
    satellite_NORAD_ID = int(satellite_answer["satellite_NORAD_ID"])

    profile_question = [
        {
            "type": "list",
            "name": "mission_profile_name",
            "message": "Which mission profile would you like to use?",
            "choices": get_mission_profile_list(gs_client),
        }
    ]

    profile_answer = prompt(profile_question)["mission_profile_name"]
    if profile_answer == "Exit":
        print("No mission profile selected. Exiting to main menu.")
        main()
    mission_profile_name = profile_answer.split("--")[0].strip()
    mission_profile_region = profile_answer.split("--")[1].strip()

    mission_profile_arn = get_mission_profile_arn(gs_client, mission_profile_name)

    satellite_arn = get_satellite_arn(gs_client, satellite_NORAD_ID)

    satellite_id = satellite_arn.split("/")[1]

    ground_station_question = [
        {
            "type": "checkbox",
            "message": "Select the ground stations you'd like to use. Do not select any to exit.",
            "name": "checkbox_selected_groundstations",
            "choices": get_onboarded_ground_stations(
                gs_client, satellite_id, mission_profile_region
            ),
        }
    ]

    ground_station_answer = prompt(ground_station_question)
    selected_groundstations = ground_station_answer["checkbox_selected_groundstations"]
    if not selected_groundstations:
        print("No ground station selected. Exiting to main menu.")
        main()

    if any(
        "AVAILABLE" in c for c in contact_type
    ):  # or any("SCHEDULED" in c for c in contact_type):
        pass_window_start_date, pass_window_end_date = get_contact_window("future")
    else:
        pass_window_start_date, pass_window_end_date = get_contact_window("all")

    all_passes = []

    for ground_station in selected_groundstations:

        pass_list = gs_client.list_contacts(
            endTime=pass_window_end_date,
            groundStation=ground_station,
            maxResults=pass_number,
            missionProfileArn=mission_profile_arn,
            satelliteArn=satellite_arn,
            startTime=pass_window_start_date,
            statusList=contact_type,
        )

        all_passes.append(pass_list["contactList"])

    flat_passes = [item for sublist in all_passes for item in sublist]

    flat_passes.sort(key=lambda item: item["startTime"], reverse=False)

    return flat_passes, mission_profile_arn, satellite_arn


class ElevationValidator(Validator):
    def validate(self, document):
        ok = regex.match("^[1-8][0-9]?$|^90$", document.text)
        if not ok:
            raise ValidationError(
                message="Please enter a valid elevation degree value [1-90]",
                cursor_position=len(document.text),
            )


class DurationValidator(Validator):
    def validate(self, document):
        ok = regex.match("^[1-9]$|^0[1-9]$|^1[0-9]$|^20$", document.text)
        if not ok:
            raise ValidationError(
                message="Please enter a valid contact duration in minutes [1-20]",
                cursor_position=len(document.text),
            )


def print_selected_contacts(selected_pass, whole_duration_answer, contact_seconds):

    selected_contact_start_date = selected_pass.split("--")[0].strip()

    selected_pass_start_time = selected_pass.split("--")[1].strip()

    selected_pass_end_time = selected_pass.split("--")[2].strip()

    selected_contact_groundstation = selected_pass.split("--")[4].strip()

    selected_contact_region = selected_pass.split("--")[5].strip()

    selected_contact_elevation = selected_pass.split("--")[6].strip()

    if whole_duration_answer:

        selected_contact_start_time = selected_pass_start_time

        selected_contact_start_datetime = datetime.datetime.strptime(
            (selected_contact_start_date + " " + selected_contact_start_time),
            "%Y-%m-%d %H:%M:%S%z",
        )

        selected_contact_end_datetime = datetime.datetime.strptime(
            (selected_contact_start_date + " " + selected_pass_end_time),
            "%Y-%m-%d %H:%M:%S%z",
        )

        selected_contact_end_time = str(selected_contact_end_datetime).split(" ")[1]

        selected_contact_duration = selected_pass.split("--")[3].strip()

    else:

        pass_duration = datetime.datetime.strptime(
            selected_pass_end_time, "%H:%M:%S%z"
        ) - datetime.datetime.strptime(selected_pass_start_time, "%H:%M:%S%z")

        contact_duration = datetime.timedelta(minutes=int(contact_seconds / 60))

        # schedule contact in the middle of the pass
        contact_offset = (pass_duration - contact_duration) / 2
        contact_offset = contact_offset - datetime.timedelta(
            microseconds=contact_offset.microseconds
        )
        selected_contact_duration = str(contact_duration)

        selected_contact_start_time = str(
            datetime.datetime.strptime(selected_pass_start_time, "%H:%M:%S%z")
            + contact_offset
        ).split(" ")[1]

        selected_contact_start_datetime = datetime.datetime.strptime(
            (selected_contact_start_date + " " + selected_contact_start_time),
            "%Y-%m-%d %H:%M:%S%z",
        )

        selected_contact_end_time = str(
            datetime.datetime.strptime(selected_pass_end_time, "%H:%M:%S%z")
            - contact_offset
        ).split(" ")[1]

        selected_contact_end_datetime = datetime.datetime.strptime(
            (selected_contact_start_date + " " + selected_contact_end_time),
            "%Y-%m-%d %H:%M:%S%z",
        )

    selected_contact_details = (
        selected_contact_start_date
        + "  --  "
        + selected_contact_start_time
        + "  --  "
        + selected_contact_end_time
        + "  --  "
        + selected_contact_duration.ljust(8)
        + "  --  "
        + selected_contact_groundstation.ljust(14)
        + "  --  "
        + selected_contact_region.ljust(22)
        + "  --  "
        + selected_contact_elevation
    )

    print(selected_contact_details)

    return (
        selected_contact_start_datetime,
        selected_contact_end_datetime,
        selected_contact_groundstation,
    )


def schedule_contact(gs_client):

    suitable_passes = []
    pass_duration_list = []

    pass_list, mission_profile_arn, satellite_arn = get_contacts(
        gs_client, ["AVAILABLE"]
    )

    minimum_elevation_question = [
        {
            "type": "input",
            "name": "minimum_elevation",
            "message": "Enter the minimum elevation requirement in degrees",
            "validate": ElevationValidator,
        }
    ]

    minimum_elevation_answer = prompt(minimum_elevation_question)
    minimum_elevation = float(minimum_elevation_answer["minimum_elevation"])

    whole_duration = [
        {
            "type": "confirm",
            "message": "Would you like to use the whole pass for the contact?",
            "name": "whole_duration",
            "default": True,
        }
    ]

    whole_duration_answer = prompt(whole_duration)["whole_duration"]

    if not whole_duration_answer:

        print(
            "Contacts shorter than the complete pass are scheduled in the middle of the contact window to maximize elevation."
        )

        contact_minutes_question = [
            {
                "type": "input",
                "name": "contact_minutes",
                "message": "Enter the required contact duration in minutes",
                "validate": DurationValidator,
            }
        ]

        contact_minutes_answer = prompt(contact_minutes_question)
        contact_seconds = int(60 * float(contact_minutes_answer["contact_minutes"]))

    for _pass in pass_list:

        if _pass["maximumElevation"]["value"] >= minimum_elevation:
            pass_duration = _pass["endTime"] - _pass["startTime"]
            pass_duration_list.append(pass_duration)
            if whole_duration_answer:
                suitable_passes.append(_pass)
            elif (
                not whole_duration_answer
            ) and pass_duration.seconds > contact_seconds:
                suitable_passes.append(_pass)

    if suitable_passes:

        padding = 45

        if whole_duration_answer:
            print(
                f"There are {len(suitable_passes)} passes that meet the {minimum_elevation} degree elevation duration requirements."
            )
            contact_seconds = 0
        else:
            print(
                f"There are {len(suitable_passes)} passes that meet the {minimum_elevation} degree elevation and {contact_seconds/60} minutes duration requirements."
            )

        pass_time_question = [
            {
                "type": "checkbox",
                "message": "Select the passes you'd like to use. Do not select any to exit.",
                "name": "checkbox_selected_passes",
                "choices": get_pass_details(suitable_passes),
            }
        ]

        pass_time_answer = prompt(pass_time_question)
        selected_passes = pass_time_answer["checkbox_selected_passes"]
        if not selected_passes:
            print("No passed selected. Exiting to main menu.")
            main()

        contact_count = 1

        print(
            "\n=============================================================Listing selected contacts==============================================================================="
        )
        print(
            "     Date   --    Start time    --     End time     --  Duration  --  Ground station  --  Mission Profile Region  --  Max Elevation (deg.)"
        )

        for selected_pass in selected_passes:

            print_selected_contacts(
                selected_pass, whole_duration_answer, contact_seconds
            )

            contact_count = contact_count + 1

        confirmation = [
            {
                "type": "confirm",
                "message": "Are you sure you want to schedule these contacts?",
                "name": "continue",
                "default": True,
            }
        ]

        confirmation_answer = prompt(confirmation)

        if confirmation_answer["continue"]:

            contact_count = 1

            for selected_pass in selected_passes:

                print("Scheduling contact")

                print(
                    "     Date   --    Start time    --     End time     --  Duration  --  Ground station  --  Mission Profile Region  --  Max Elevation (deg.)"
                )

                (
                    selected_contact_start_datetime,
                    selected_contact_end_datetime,
                    selected_contact_groundstation,
                ) = print_selected_contacts(
                    selected_pass, whole_duration_answer, contact_seconds
                )

                # Canceling on demand contacts incurs their full cost!
                reservation = gs_client.reserve_contact(
                    endTime=selected_contact_end_datetime,
                    groundStation=selected_contact_groundstation,
                    missionProfileArn=mission_profile_arn,
                    satelliteArn=satellite_arn,
                    startTime=selected_contact_start_datetime,
                )

                contact_Id = reservation["contactId"]
                print(f"Scheduled contact ID: {contact_Id}")

                contact_count = contact_count + 1

            main()
        else:
            print("No contacts scheduled. Exiting to main menu.")
            main()

    else:
        print(
            f"NO AVAILABLE passes that meet {minimum_elevation} degree elevation and {int(contact_seconds/60)}:00 minutes duration requirements."
        )
        print(
            "The longest pass duration in this window is "
            + str(max(pass_duration_list)).split("0:")[1]
            + " minutes"
        )


def view_contact(gs_client, cancel=False):

    scheduled_contacts = []

    if cancel:
        responce = get_contacts(gs_client, ["SCHEDULED"])[0]
    else:
        responce = get_contacts(
            gs_client,
            [
                "SCHEDULED",
                "SCHEDULING",
                "FAILED_TO_SCHEDULE",
                "AWS_CANCELLED",
                "CANCELLED",
                "COMPLETED",
                "FAILED",
                "AWS_CANCELLED",
                "AWS_FAILED",
                "CANCELLED",
                "FAILED_TO_SCHEDULE",
            ],
        )[0]

    if bool(responce):
        print(
            "\n====================================================================================================Listing contacts================================================================================================================="
        )
        print(
            "     Date   --    Start time    --     End time     --  Duration  --  Ground station  --  Mission Profile Name  --  Mission Profile Region  --  Max Elevation (deg.)  -- Contact Status     -- Contact ID"
        )
        for contact in responce:

            duration = contact["endTime"] - contact["startTime"]

            mission_profile_name = get_mission_profile_name(
                gs_client, contact["missionProfileArn"]
            )

            contact_details = (
                str(contact["startTime"].astimezone(tz=datetime.timezone.utc).date())
                + "  --  "
                + str(contact["startTime"].astimezone(tz=datetime.timezone.utc)).split(
                    " "
                )[1]
                + "  --  "
                + str(contact["endTime"].astimezone(tz=datetime.timezone.utc)).split(
                    " "
                )[1]
                + "  --  "
                + str(duration).ljust(8)
                + "  --  "
                + str(contact["groundStation"]).ljust(14)
                + "  --  "
                + str(mission_profile_name).ljust(20)
                + "  --  "
                + str(contact["region"]).ljust(22)
                + "  --  "
                + str(contact["maximumElevation"]["value"]).ljust(20)
                + "  --  "
                + str(contact["contactStatus"]).ljust(16)
                + "  --  "
                + str(contact["contactId"])
            )
            print(contact_details)
            scheduled_contacts.append({"name": contact_details})
        print()

    else:
        print("\nNo scheduled contacts with specified parameters.\n")

    return scheduled_contacts, responce


def cancel_contact(gs_client):

    scheduled_contacts, responce = view_contact(gs_client, cancel=True)

    print()

    if bool(scheduled_contacts):

        cancel_question = [
            {
                "type": "checkbox",
                "message": "Select the contacts you'd like to cancel. Do not select any to exit.",
                "name": "checkbox_canceled_contacts",
                "choices": scheduled_contacts,
            }
        ]

        cancel_answer = prompt(cancel_question)
        contacts_to_cancel = cancel_answer["checkbox_canceled_contacts"]
        if not contacts_to_cancel:
            print("No contacts selected. Exiting to main menu.")
            main()

        print(
            "\n=============================================================================================Listing contacts to cancel============================================================================================================"
        )
        print(
            "     Date   --    Start time    --     End time     --  Duration  --  Ground station  --  Mission Profile Name  --  Mission Profile Region  --  Max Elevation (deg.)  -- Contact Status     -- Contact ID"
        )

        for target_contact in contacts_to_cancel:

            target_contact_start_date = target_contact.split("--")[0].strip()
            target_contact_start_time = target_contact.split("--")[1].strip()
            target_contact_start_datetime = datetime.datetime.strptime(
                (target_contact_start_date + " " + target_contact_start_time),
                "%Y-%m-%d %H:%M:%S%z",
            )

            for contact in responce:
                if contact["startTime"] == target_contact_start_datetime:
                    contact_Id = contact["contactId"]
                    mission_profile_name = get_mission_profile_name(
                        gs_client, contact["missionProfileArn"]
                    )
                    duration = contact["endTime"] - contact["startTime"]
                    contact_details = (
                        str(
                            contact["startTime"]
                            .astimezone(tz=datetime.timezone.utc)
                            .date()
                        )
                        + "  --  "
                        + str(
                            contact["startTime"].astimezone(tz=datetime.timezone.utc)
                        ).split(" ")[1]
                        + "  --  "
                        + str(
                            contact["endTime"].astimezone(tz=datetime.timezone.utc)
                        ).split(" ")[1]
                        + "  --  "
                        + str(duration).ljust(8)
                        + "  --  "
                        + str(contact["groundStation"]).ljust(14)
                        + "  --  "
                        + str(mission_profile_name).ljust(20)
                        + "  --  "
                        + str(contact["region"]).ljust(22)
                        + "  --  "
                        + str(contact["maximumElevation"]["value"]).ljust(20)
                        + "  --  "
                        + str(contact["contactStatus"]).ljust(16)
                        + "  --  "
                        + str(contact["contactId"])
                    )
                    print(contact_details)

        confirmation = [
            {
                "type": "confirm",
                "message": "Are you sure you want to cancel these contacts?",
                "name": "continue",
                "default": True,
            }
        ]

        confirmation_answer = prompt(confirmation)

        if confirmation_answer["continue"]:

            for target_contact in contacts_to_cancel:

                target_contact_start_date = target_contact.split("--")[0].strip()
                target_contact_start_time = target_contact.split("--")[1].strip()
                target_contact_start_datetime = datetime.datetime.strptime(
                    (target_contact_start_date + " " + target_contact_start_time),
                    "%Y-%m-%d %H:%M:%S%z",
                )

                for contact in responce:
                    if contact["startTime"] == target_contact_start_datetime:
                        contact_Id = contact["contactId"]
                        duration = contact["endTime"] - contact["startTime"]
                        mission_profile_name = get_mission_profile_name(
                            gs_client, contact["missionProfileArn"]
                        )
                        print("Cancelling contact")
                        print(
                            "     Date   --    Start time    --     End time     --  Duration  --  Ground station  --  Mission Profile Name  --  Mission Profile Region  --  Max Elevation (deg.)  -- Contact Status     -- Contact ID"
                        )
                        contact_details = (
                            str(
                                contact["startTime"]
                                .astimezone(tz=datetime.timezone.utc)
                                .date()
                            )
                            + "  --  "
                            + str(
                                contact["startTime"].astimezone(
                                    tz=datetime.timezone.utc
                                )
                            ).split(" ")[1]
                            + "  --  "
                            + str(
                                contact["endTime"].astimezone(tz=datetime.timezone.utc)
                            ).split(" ")[1]
                            + "  --  "
                            + str(duration).ljust(8)
                            + "  --  "
                            + str(contact["groundStation"]).ljust(14)
                            + "  --  "
                            + str(mission_profile_name).ljust(20)
                            + "  --  "
                            + str(contact["region"]).ljust(22)
                            + "  --  "
                            + str(contact["maximumElevation"]["value"]).ljust(20)
                            + "  --  "
                            + str(contact["contactStatus"]).ljust(16)
                            + "  --  "
                            + str(contact["contactId"])
                        )
                        print(contact_details)

                        cancellation = gs_client.cancel_contact(contactId=contact_Id)

                        print(
                            "Successfully canceled contact with ID: "
                            + cancellation["contactId"]
                        )
                        print()

            main()
        else:
            print("No contacts canceled. Exiting to main menu.")
            main()


def main():

    gs_client = boto3.client("groundstation")

    task_question = [
        {
            "type": "list",
            "name": "task",
            "message": "What would you like to do?",
            "choices": [
                "Schedule contacts",
                "View contacts",
                "Cancel contacts",
                "Quit",
            ],
        }
    ]

    task_answer = prompt(task_question)
    task = task_answer["task"]

    if task == "Schedule contacts":
        schedule_contact(gs_client)
    elif task == "View contacts":
        view_contact(gs_client)
    elif task == "Cancel contacts":
        cancel_contact(gs_client)
    elif task == "Quit":
        quit()

    main()


if __name__ == "__main__":
    main()
