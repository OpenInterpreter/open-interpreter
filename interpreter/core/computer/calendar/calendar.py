import datetime
import platform
import subprocess

from ..utils.run_applescript import run_applescript, run_applescript_capture

makeDateFunction = """
on makeDate(yr, mon, day, hour, min, sec)
	set theDate to current date
	tell theDate
		set its year to yr
		set its month to mon
		set its day to day
		set its hours to hour
		set its minutes to min
		set its seconds to sec
	end tell
	return theDate
end makeDate
"""


class Calendar:
    def __init__(self, computer):
        self.computer = computer
        # In the future, we might consider a way to use a different calendar app. For now its Calendar
        self.calendar_app = "Calendar"

    def get_events(self, start_date=datetime.date.today(), end_date=None):
        """
        Fetches calendar events for the given date or date range.
        """
        if platform.system() != "Darwin":
            return "This method is only supported on MacOS"

        if not end_date:
            end_date = start_date
        # AppleScript command
        script = f"""
        {makeDateFunction}
        set theDate to makeDate({start_date.strftime("%Y, %m, %d, 0, 0, 0")})
        set endDate to makeDate({end_date.strftime("%Y, %m, %d, 23, 59, 59")})
        tell application "System Events"
            set calendarIsRunning to (name of processes) contains "{self.calendar_app}"
            if calendarIsRunning then
                tell application "{self.calendar_app}" to activate
            else
                tell application "{self.calendar_app}" to launch
                delay 1 -- Wait for the application to open
                tell application "{self.calendar_app}" to activate
            end if
        end tell

        set outputText to ""

        -- Access the Calendar app
        tell application "{self.calendar_app}"
            
            -- Initialize a list to hold summaries and dates of all events from all calendars
            set allEventsInfo to {{}}
            
            -- Loop through each calendar
            repeat with aCalendar in calendars
                
                -- Fetch events from this calendar that fall within the specified date range
                set theseEvents to (every event of aCalendar where its start date is greater than theDate and its start date is less than endDate)
                
                -- Loop through theseEvents to extract necessary details
                repeat with anEvent in theseEvents
                    -- Initialize variables to "None" to handle missing information gracefully
                    set attendeesString to "None"
                    set theNotes to "None"
                    set theLocation to "None"
                    
                    -- Try to get attendees, but fail gracefully
                    try
                        set attendeeNames to {{}}
                        repeat with anAttendee in attendees of anEvent
                            set end of attendeeNames to name of anAttendee
                        end repeat
                        if (count of attendeeNames) > 0 then
                            set attendeesString to my listToString(attendeeNames, ", ")
                        end if
                    on error
                        set attendeesString to "None"
                    end try
                    
                    -- Try to get notes, but fail gracefully
                    try
                        set theNotes to notes of anEvent
                        if theNotes is missing value then set theNotes to "None"
                    on error
                        set theNotes to "None"
                    end try
                    
                    -- Try to get location, but fail gracefully
                    try
                        set theLocation to location of anEvent
                        if theLocation is missing value then set theLocation to "None"
                    on error
                        set theLocation to "None"
                    end try
                    
                    -- Create a record with the detailed information of the event
                    set eventInfo to {{|summary|:summary of anEvent, |startDate|:start date of anEvent, |endDate|:end date of anEvent, |attendees|:attendeesString, notes:theNotes, |location|:theLocation}}
                    -- Append this record to the allEventsInfo list
                    set end of allEventsInfo to eventInfo
                end repeat
            end repeat
        end tell

        -- Check if any events were found and build the output text
        if (count of allEventsInfo) > 0 then
            repeat with anEventInfo in allEventsInfo
                -- Always include Event, Start Date, and End Date
                set eventOutput to "Event: " & (summary of anEventInfo) & " | Start Date: " & (|startDate| of anEventInfo) & " | End Date: " & (|endDate| of anEventInfo)
                
                -- Conditionally include other details if they are not "None"
                if (attendees of anEventInfo) is not "None" then
                    set eventOutput to eventOutput & " | Attendees: " & (attendees of anEventInfo)
                end if
                if (notes of anEventInfo) is not "None" then
                    set eventOutput to eventOutput & " | Notes: " & (notes of anEventInfo)
                end if
                if (location of anEventInfo) is not "None" then
                    set eventOutput to eventOutput & " | Location: " & (location of anEventInfo)
                end if
                
                -- Add the event's output to the overall outputText, followed by a newline for separation
                set outputText to outputText & eventOutput & "
        "
            end repeat
        else
            set outputText to "No events found for the specified date."
        end if

        -- Return the output text
        return outputText

        -- Helper subroutine to convert a list to a string
        on listToString(theList, delimiter)
            set AppleScript's text item delimiters to delimiter
            set theString to theList as string
            set AppleScript's text item delimiters to ""
            return theString
        end listToString

        """

        # Get outputs from AppleScript
        stdout, stderr = run_applescript_capture(script)
        if stderr:
            # If the error is due to not having access to the calendar app, return a helpful message
            if "Not authorized to send Apple events to Calendar" in stderr:
                return "Calendar access not authorized. Please allow access in System Preferences > Security & Privacy > Automation."
            else:
                return stderr

        return stdout

    def create_event(
        self,
        title: str,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        location: str = "",
        notes: str = "",
        calendar: str = None,
    ) -> str:
        """
        Creates a new calendar event in the default calendar with the given parameters using AppleScript.
        """
        if platform.system() != "Darwin":
            return "This method is only supported on MacOS"

        # Format datetime for AppleScript
        applescript_start_date = start_date.strftime("%B %d, %Y %I:%M:%S %p")
        applescript_end_date = end_date.strftime("%B %d, %Y %I:%M:%S %p")

        # If there is no calendar, lets use the first calendar applescript returns. This should probably be modified in the future
        if calendar is None:
            calendar = self.get_first_calendar()
            if calendar is None:
                return "Can't find a default calendar. Please try again and specify a calendar name."

        script = f"""
        {makeDateFunction}
        set startDate to makeDate({start_date.strftime("%Y, %m, %d, %H, %M, %S")})
        set endDate to makeDate({end_date.strftime("%Y, %m, %d, %H, %M, %S")})
        -- Open and activate calendar first
        tell application "System Events"
            set calendarIsRunning to (name of processes) contains "{self.calendar_app}"
            if calendarIsRunning then
                tell application "{self.calendar_app}" to activate
            else
                tell application "{self.calendar_app}" to launch
                delay 1 -- Wait for the application to open
                tell application "{self.calendar_app}" to activate
            end if
        end tell
        tell application "{self.calendar_app}"
            tell calendar "{calendar}"
                make new event at end with properties {{summary:"{title}", start date:startDate, end date:endDate, location:"{location}", description:"{notes}"}}
            end tell
            -- tell the Calendar app to refresh if it's running, so the new event shows up immediately
            tell application "{self.calendar_app}" to reload calendars
        end tell
        """

        try:
            run_applescript(script)
            return f"""Event created successfully in the "{calendar}" calendar."""
        except subprocess.CalledProcessError as e:
            return str(e)

    def delete_event(
        self, event_title: str, start_date: datetime.datetime, calendar: str = None
    ) -> str:
        if platform.system() != "Darwin":
            return "This method is only supported on MacOS"

        # The applescript requires a title and start date to get the right event
        if event_title is None or start_date is None:
            return "Event title and start date are required"

        # If there is no calendar, lets use the first calendar applescript returns. This should probably be modified in the future
        if calendar is None:
            calendar = self.get_first_calendar()
            if not calendar:
                return "Can't find a default calendar. Please try again and specify a calendar name."

        script = f"""
        {makeDateFunction}
        set eventStartDate to makeDate({start_date.strftime("%Y, %m, %d, %H, %M, %S")})
        -- Open and activate calendar first
        tell application "System Events"
            set calendarIsRunning to (name of processes) contains "{self.calendar_app}"
            if calendarIsRunning then
                tell application "{self.calendar_app}" to activate
            else
                tell application "{self.calendar_app}" to launch
                delay 1 -- Wait for the application to open
                tell application "{self.calendar_app}" to activate
            end if
        end tell
        tell application "{self.calendar_app}"
            -- Specify the name of the calendar where the event is located
            set myCalendar to calendar "{calendar}"
            
            -- Define the exact start date and name of the event to find and delete
            set eventSummary to "{event_title}"
            
            -- Find the event by start date and summary
            set theEvents to (every event of myCalendar where its start date is eventStartDate and its summary is eventSummary)
            
            -- Check if any events were found
            if (count of theEvents) is equal to 0 then
                return "No matching event found to delete."
            else
                -- If the event is found, delete it
                repeat with theEvent in theEvents
                    delete theEvent
                end repeat
                save
                return "Event deleted successfully."
            end if
        end tell
        """

        stderr, stdout = run_applescript_capture(script)
        if stdout:
            return stdout[0].strip()
        elif stderr:
            if "successfully" in stderr:
                return stderr

            return f"""Error deleting event: {stderr}"""
        else:
            return "Unknown error deleting event. Please check event title and date."

    def get_first_calendar(self) -> str:
        # Literally just gets the first calendar name of all the calendars on the system. AppleScript does not provide a way to get the "default" calendar
        script = f"""
            -- Open calendar first
            tell application "System Events"
                set calendarIsRunning to (name of processes) contains "{self.calendar_app}"
                if calendarIsRunning is false then
                    tell application "{self.calendar_app}" to launch
                    delay 1 -- Wait for the application to open
                end if
            end tell
            tell application "{self.calendar_app}"
            -- Get the name of the first calendar
                set firstCalendarName to name of first calendar
            end tell
            return firstCalendarName
            """
        stdout = run_applescript_capture(script)
        if stdout:
            return stdout[0].strip()
        else:
            return None
