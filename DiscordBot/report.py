from enum import Enum, auto
import discord
import re
import datetime
from collections import defaultdict

class State(Enum):
    REPORT_START = auto()
    AWAITING_MESSAGE = auto()
    AWAITING_CONFIRMATION = auto()      # Custom State, used to verify message before reporting flow.
    MESSAGE_IDENTIFIED = auto()
    FLOW_IDENTIFIED = auto()            # Custom State, used to track which flow we are under
    REPORT_COMPLETE = auto()

class Report:
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"

    def __init__(self, client):
        self.state = State.REPORT_START
        self.client = client
        self.message = None             # Store offending message information (poster, content, etc)
        self.report = {                 # Persist details of the report
            "reporter" : None,
            "type" : None,
            "date" : None,
            "params" : defaultdict(lambda: None)
        }                
    
    async def handle_message(self, message):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord. 
        '''

        # Perform some message preprocessing here:
        user_message = str.lower(str(message.content))    # Parse lowered version of the message 

        if user_message == self.CANCEL_KEYWORD:
            self.state = State.REPORT_COMPLETE
            return ["Report cancelled."]

        elif self.state == State.REPORT_START:
            reply =  "Thank you for starting the reporting process. "
            reply += "Say `help` at any time for more information.\n\n"
            reply += "Please copy paste the link to the message you want to report.\n"
            reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."
            
            # Update current state and initialize report
            self.state = State.AWAITING_MESSAGE
            self.report['reporter'] = message.author
            self.report['date'] = datetime.datetime.now()

            return [reply]
        
        elif self.state == State.AWAITING_MESSAGE:
            # Parse out the three ID strings from the message link
            m = re.search('/(\d+)/(\d+)/(\d+)', message.content)
            if not m:
                return ["I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel."]
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return ["I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again."]
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                return ["It seems this channel was deleted or never existed. Please try again or say `cancel` to cancel."]
            
            # Fetch actual message from channel
            try:
                message = await channel.fetch_message(int(m.group(3)))
            except discord.errors.NotFound:
                return ["It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."]

            # Here we've found the message - it's up to you to decide what to do next!
            self.state = State.AWAITING_CONFIRMATION
            self.message = message
            return ["I found this message:", "```" + message.author.name + ": " + message.content + "```", \
                    "Please reply `YES` if the message and author are correct, `NO` if not, or `cancel` to cancel."]
        
        elif self.state == State.AWAITING_CONFIRMATION:
            # Perform message confirmation before beginning the reporting flow

            if user_message == "yes":
                self.state = State.MESSAGE_IDENTIFIED

                reply = "Thank you for reporting! Please indicate the number of the type of abuse below that this message falls under:\n\n"
                reply += "1.) Fraud \n"
                reply += "2.) Solicitation \n"
                reply += "3.) Impersonation \n"
                reply += "4.) Violence and/or Harmful Behavior \n"
                reply += "5.) Just makes me uncomfortable / Other"

            elif user_message == "no":
                self.state = State.AWAITING_MESSAGE

                reply = "Restarting reporting service..\n\n Please copy paste the link to the message you want to report.\n"
                reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."

            else:
                reply = "Sorry this input is invalid.\n"
                reply += "Please reply `YES` if the message and author are correct, `NO` if not, or `cancel` to cancel."

        elif self.state == State.MESSAGE_IDENTIFIED:
            # BEGIN USER FLOW: Identify which flow to follow for this report.

            # Regex to extract numbers in message content
            temp = re.findall(r'\d+', message.content)
            option = str(list(map(int, temp)))
            report_type = ""

            # Extract report type
            if option == 1:
                report_type = 'Fraud'
            elif option == 2:
                report_type = 'Soliciation'
            elif option == 3:
                report_type = 'Impersonation'
            elif option == 4:
                report_type = 'Violence and/or Harmful Behavior'
            elif option == 5:
                report_type = 'Uncomfortable / Other'
            else:
                reply = 'Sorry, please indicate an option between 1-5. \n'
                reply += 'Please choose option 5 if the four other categories do not match your desired category.'
                return [reply]

            # Store report type and continue flow based on action.
            self.report['type'] = report_type
            self.state = State.FLOW_IDENTIFIED

            reply = f"Thank you for reporting this message as `{report_type}`.\n"
            reply += "Please reply with `OK` to continue the reporting process!"

        elif self.state == State.FLOW_IDENTIFIED:
            report_type = self.report['type']
            params = self.report['params']

            if report_type == 'Fraud':
                reply = self.fraud_flow(params)
            elif report_type == 'Solicitation':
                pass
            elif report_type == 'Impersonation':
                pass
            elif report_type == 'Violence and/or Harmful Behavior':
                pass
            else:
                pass

        return [reply]

    def report_complete(self):
        return self.state == State.REPORT_COMPLETE
    
    ### Create each flow as their own methods

    def fraud_flow(self, params : dict):
        """
        This function handles the Fraud flow specifically, for better code visibility in the main handler function.
        """
        action, has_leaked_info, has_shared_logs, req_to_block = params.values()
        return ""

