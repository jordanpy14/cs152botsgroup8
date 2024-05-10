"""
Team 8
Colette Do
Carlo Dino
Christian Gebhardt
Euysun Hwang
Jordan Paredes
"""

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
    REPORT_CANCELLED = auto()

class Report:
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"

    def __init__(self, client):
        self.state = State.REPORT_START
        self.client = client
        self.report_cancelled = False
        self.message = None             # Store offending message information (poster, content, etc)
        self.report = {                 # Persist details of the report, anything to be saved goes here, saving is handled by the bot.
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
        reply = ""

        if user_message == self.CANCEL_KEYWORD:
            self.state = State.REPORT_COMPLETE
            self.report_cancelled = True
            return ["Report cancelled."]

        elif self.state == State.REPORT_START:
            reply =  "Thank you for starting the reporting process. "
            reply += "Say `help` at any time for more information.\n\n"
            reply += "Please copy paste the link to the message you want to report.\n"
            reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."
            
            # Update current state and initialize report
            self.state = State.AWAITING_MESSAGE
            self.report['reporter'] = message.author.id
            self.report['date'] = datetime.datetime.now().isoformat()

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
            print("Found message: ", message)
            self.message = message
            return ["I found this message:", "```" + message.author.name + ": " + message.content + "```", \
                    "Please reply `YES` if the message and author are correct, `NO` if not, or `cancel` to cancel."]
        
        elif self.state == State.AWAITING_CONFIRMATION:
            # Perform message confirmation before beginning the reporting flow

            if user_message == "yes":
                self.state = State.MESSAGE_IDENTIFIED

                reply = "Thank you for reporting! Please indicate the number of the type of abuse below that this message falls under:\n\n"
                reply += "**1.) Fraud** \n\n"
                reply += "**2.) Solicitation** \n\n"
                reply += "**3.) Impersonation** \n\n"
                reply += "**4.) Violence and/or Harmful Behavior** \n\n"
                reply += "**5.) Just makes me uncomfortable / Other** \n"

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
            option = list(map(int, temp))[0]
            report_type = ""

            # Extract report type
            if option == 1:
                report_type = 'Fraud'
            elif option == 2:
                report_type = 'Solicitation'
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
            is_complete = False

            if report_type == 'Fraud':
                reply = await self.fraud_flow(user_message, params)                
            elif report_type == 'Solicitation':
                reply = await self.solicitation_flow(user_message, params)
            elif report_type == 'Impersonation':
                reply = await self.impersonation_flow(user_message, params)
            elif report_type == 'Violence and/or Harmful Behavior':
                reply = await self.violence_behavior_flow(user_message, params)
            else:
                reply = await self.uncomfortable_other_flow(user_message, params)

            if params['completed']:
                self.state = State.REPORT_COMPLETE


        elif self.state == State.REPORT_COMPLETE:
            # Notify moderation team of report, send to mod chat.
            # TODO
            print("TODO")

        return [reply]

    def report_complete(self):
        return self.state == State.REPORT_COMPLETE
    
    ### Create each flow as their own methods

    async def fraud_flow(self, user_message : str, params : dict):
        """
        This function handles the Fraud flow specifically, for better code visibility in the main handler function.
        """
        action = params['action']
        has_leaked_info = params['has_leaked_info']
        has_shared_logs = params['has_shared_logs']
        req_to_block = params['req_to_block']
        params['completed'] = False
        is_complete = params['completed']

        reply = ""

        if action is None:
            reply = "Please indicate what method of fraud is perpetrated in the reported message (if multiple apply, please indicate all relevant numbers with commas as: X,Y,Z):\n\n"
            reply += "**1.) Sending suspicious and/or malicious off-site URLs**\n"
            reply += "    - This mostly pertains to fake URLs such as co1nbas3.com.xyz (Fake Coinbase) and secure.chase.com.xyz (Fake Chase)\n\n"
            reply += "**2.) Suggesting a cryptocurrency-type scheme**\n"
            reply += "    - This includes pump-and-dump schemes, sending crypto to unknown wallets, and links to fake cryptocurrency exchanges.\n\n"
            reply += "**3.) Asking for highly confidentrial personal information**\n"
            reply += "    - Some notable examples are your SSN, credit card numbers, and home addresses\n"

            # Update action state to empty string, while waiting for response
            params['action'] = ""
        
        elif has_leaked_info is None:

            # Regex to extract numbers in message content and update params
            temp = re.findall(r'\d+', user_message)
            options = list(map(int, temp))
            for option in options:
                text = ""
                if option == 1:
                    text = "Fraud: URL,\n"
                elif option == 2:
                    text = "Fraud: Crypto,\n"
                elif option == 3:
                    text = "Fraud: Personal Information,\n"
                else:
                    continue

                params["action"] += text

            reply = "Please indicate whether or not the reported fraud has occurred already.\n"
            reply += "- If you have already fallen victim to the reported fraud, our moderation team can connect you to resources to protect your identity and recover assets.\n"
            reply += "Please reply with `YES` or `NO` below:"
            
            # Update parameter to non-None type to continue
            params["has_leaked_info"] = ""

        elif has_shared_logs is None:
            
            # Update has_leaked_info param based on user_message
            if user_message == "yes":
                params["has_leaked_info"] = True
            elif user_message == "no":
                params["has_leaked_info"] = False
            else:
                return "Please reply with `YES` or `NO` below:"

            reply = "Please indicate whether or not you would like to include your chat history in this report.\n"
            reply += "Please reply with `YES` or `NO` below:"

            # Update parameter to non-None type to continue
            params["has_shared_logs"] = ""

        elif req_to_block is None:
            
            # Update has_shared_logs param based on user_message
            if user_message == "yes":
                params["has_shared_logs"] = True
            elif user_message == "no":
                params["has_shared_logs"] = False
            else:
                return "Please reply with `YES` or `NO` below:"
            
            # Initialize an array of DiscordMessages in params
            params['logs'] = []

            if params["has_shared_logs"]:
                reply = "Please continuously copy paste the link to the messages in your chat history that you want to report.\n"
                reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`.\n"
                reply += "When you are done, please enter `Complete` to indicate so."
            else:
                reply = "Please enter `Complete` to confirm no additional messages."

            # Update parameter to non-None type to continue
            params['req_to_block'] = ""

        elif params['logs'] is not None and user_message != 'complete' and req_to_block == "":

            # Parse out the three ID strings from the message link
            m = re.search('/(\d+)/(\d+)/(\d+)', user_message)
            if not m:
                return "I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel."
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return "I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again."
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                return "It seems this channel was deleted or never existed. Please try again or say `cancel` to cancel."

            # Fetch actual message from channel
            try:
                new_message = await channel.fetch_message(int(m.group(3)))
                params['logs'].append(new_message)
            except discord.errors.NotFound:
                return "It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."

            reply = "Received this message:```" + new_message.author.name + ": " + new_message.content + "```\n"
            reply += "Please continuously copy paste the link to the messages in your chat history that you want to report.\n"
            reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`.\n"
            reply += "When you are done, please enter `Complete` to indicate so."

        elif req_to_block == "":
            reply = "Thank you for filling out this report! We have finalized the reporting process and will notify our moderation team shortly.\n"
            reply += "For now, please indicate whether or not you would like the reported user blocked. \n"
            reply += "- Blocked users will not be notified that they are blocked and you will no longer receive any communications from them.\n\n"
            reply += "Please reply with `YES` or `NO` below:\n"
            
            # Update parameter to new type to continue
            params["completed"]
            params["req_to_block"] = -1

        elif req_to_block == -1:
            # Update req_to_block param based on user_message
            if user_message == "yes":
                params["req_to_block"] = True
            elif user_message == "no":
                params["req_to_block"] = False
            else:
                return "Please reply with `YES` or `NO` below:"

            reply = "Thank you for your time, have a great rest of your day!"
            params["completed"] = True
        
        else:
            # Should never get here
            reply = "Fraud Report Complete."
            params["completed"] = True

        return reply
    
    async def violence_behavior_flow(self, user_message : str, params : dict):
        """
        This function handles the Violence and/or Harmful Behavior flow specifically, for better code visibility in the main handler function.
        """
        action = params['action']
        req_to_block = params['req_to_block']
        params['completed'] = False

        if action is None:

            reply = "Please indicate the number this type of action falls under:\n"
            reply += "**1.) Bullying** \n\n"
            reply += "**2.) Hate speech**\n\n"
            reply += "**3.) Unwanted sexual content** \n\n"
            reply += "**4.) Violence to Others/Self Harm**\n\n"
            reply += "**5.) Other**\n"
            params['action'] = ""

        elif req_to_block is None:
            
            temp = re.findall(r'\d+', user_message)
            option = list(map(int, temp))
            if len(option) == 0:
                return 'Sorry, please indicate an option between 1-5. \n'
            option = option[0]

            if option == 1:
                params['action'] = 'Bullying'
            elif option == 2:
                params['action'] = 'Hate speech'
            elif option == 3:
                params['action'] = 'Unwanted sexual content'
            elif option == 4:
                params['action'] = 'Violence to Others/Self Harm'
            elif option == 5:
                params['action'] = 'Other'
            else:
                return 'Sorry, please indicate an option between 1-5. \n'
           
            reply = f"Thank you for reporting this message as `{params['action']}`. \n"
            reply += "Our content moderation team will review the message according to the Community Guidelines and remove the message/account if necessary.\n"
            reply += "For now, please indicate whether or not you would like the reported user blocked. \n"
            reply += "- Blocked users will not be notified that they are blocked and you will no longer receive any communications from them.\n\n"
            reply += "Please reply with `YES` or `NO` below:\n"
            params['req_to_block'] = -1
        
        elif req_to_block == -1:

            # Update req_to_block param based on user_message
            if user_message == "yes":
                params["req_to_block"] = True
            elif user_message == "no":
                params["req_to_block"] = False
            else:
                return "Please reply with `YES` or `NO` below:"

            reply = "Thank you for your time, have a great rest of your day!"
            params["completed"] = True

        else:
            # Should never get here
            reply = "Violence and/or Harmful Behavior Report Complete."
            params["completed"] = True

        return reply
    
    async def uncomfortable_other_flow(self, user_message : str, params : dict):
        """
        This function handles the Uncomfortable / Other flow specifically, for better code visibility in the main handler function.
        """
        action = params['action']
        has_shared_logs = params['has_shared_logs']
        req_to_block = params['req_to_block']
        params['completed'] = False
        is_complete = params['completed']

        reply = ""

        if action is None:
            reply = "Would you like to provide more context for the report? \n"
            reply += "Reply with more information on the abuse or `N/A`"

            # Update action state to empty string, while waiting for response
            params['action'] = ""

        elif has_shared_logs is None:
            
            params['action'] = user_message

            reply = "Please indicate whether or not you would like to include your chat history in this report.\n"
            reply += "Please reply with `YES` or `NO` below:"

            # Update parameter to non-None type to continue
            params["has_shared_logs"] = ""

        elif req_to_block is None:
            
            # Update has_shared_logs param based on user_message
            if user_message == "yes":
                params["has_shared_logs"] = True
            elif user_message == "no":
                params["has_shared_logs"] = False
            else:
                return "Please reply with `YES` or `NO` below:"
            
            # Initialize an array of DiscordMessages in params
            params['logs'] = []

            if params["has_shared_logs"]:
                reply = "Please continuously copy paste the link to the messages in your chat history that you want to report.\n"
                reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`.\n"
                reply += "When you are done, please enter `Complete` to indicate so."
            else:
                reply = "Please enter `Complete` to confirm no additional messages."

            # Update parameter to non-None type to continue
            params['req_to_block'] = ""

        elif params['logs'] is not None and user_message != 'complete' and req_to_block == "":

            # Parse out the three ID strings from the message link
            m = re.search('/(\d+)/(\d+)/(\d+)', user_message)
            if not m:
                return "I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel."
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return "I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again."
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                return "It seems this channel was deleted or never existed. Please try again or say `cancel` to cancel."

            # Fetch actual message from channel
            try:
                new_message = await channel.fetch_message(int(m.group(3)))
                params['logs'].append(new_message)
            except discord.errors.NotFound:
                return "It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."

            reply = "Received this message:```" + new_message.author.name + ": " + new_message.content + "```\n"
            reply += "Please continuously copy paste the link to the messages in your chat history that you want to report.\n"
            reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`.\n"
            reply += "When you are done, please enter `Complete` to indicate so."

        elif req_to_block == "":
            reply = "Thank you for filling out this report! We have finalized the reporting process and will notify our moderation team shortly.\n"
            reply += "For now, please indicate whether or not you would like the reported user blocked. \n"
            reply += "- Blocked users will not be notified that they are blocked and you will no longer receive any communications from them.\n\n"
            reply += "Please reply with `YES` or `NO` below:\n"
            
            # Update parameter to new type to continue
            params["completed"]
            params["req_to_block"] = -1

        elif req_to_block == -1:
            # Update req_to_block param based on user_message
            if user_message == "yes":
                params["req_to_block"] = True
            elif user_message == "no":
                params["req_to_block"] = False
            else:
                return "Please reply with `YES` or `NO` below:"

            reply = "Thank you for your time, have a great rest of your day!"
            params["completed"] = True
        
        else:
            # Should never get here
            reply = "Uncomfortable Content Report Complete."
            params["completed"] = True

        return reply

    async def solicitation_flow(self, user_message : str, params : dict):
        """
        This function handles the Solicitation flow specifically, for better code visibility in the main handler function.
        """
        action = params['action']
        has_shared_logs = params['has_shared_logs']
        req_to_block = params['req_to_block']
        params['completed'] = False
        is_complete = params['completed']

        reply = ""

        if action is None:
            reply = "Please indicate what method of solicitation is perpetrated in the reported message:\n\n"
            reply += "**1.) Attempting to redicet to external system**\n"
            reply += "    - This mostly pertains to trying to take someone to end-to-end encrypted chats like WhatsApp, Telegram etc\n\n"
            reply += "**2.) Asking for money, cryptocurrency, or giving finacial advice**\n"
            reply += "    - This includes pump-and-dump schemes, sending crypto to unknown wallets, and links to fake cryptocurrency exchanges.\n\n"

            # Update action state to empty string, while waiting for response
            params['action'] = ""
        
        elif has_shared_logs is None:

            # Regex to extract numbers in message content and update params
            temp = re.findall(r'\d+', user_message)
            options = list(map(int, temp))
            for option in options:
                text = ""
                if option == 1:
                    text = "Solicitation: Attempt to redirect to external system,\n"
                elif option == 2:
                    text = "Solicitation: asking for money or crypto,\n"
                else:
                    continue

                params["action"] += text

            reply = "Please indicate whether or not you would like to include your chat history in this report.\n"
            reply += "Please reply with `YES` or `NO` below:"
            
            # Update parameter to non-None type to continue
            params["has_shared_logs"] = ""
            has_shared_logs = params["has_shared_logs"]

        elif req_to_block is  None:
            print("user_message: ", user_message)
            
            # Update has_shared_logs param based on user_message
            if user_message == "yes":
                params["has_shared_logs"] = True
            elif user_message == "no":
                params["has_shared_logs"] = False
            else:
                return "Please reply with `YES` or `NO` below:"
            
            params['logs'] = []
            
            if params["has_shared_logs"]:
                reply = "Please continuously copy paste the link to the messages in your chat history that you want to report.\n"
                reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`.\n"
                reply += "When you are done, please enter `Complete` to indicate so."
            else:
                reply = "Please enter `Complete` to confirm no additional messages."
            
            params['req_to_block'] = ""
        elif params['logs'] is not None and user_message != 'complete' and req_to_block == "":
            # Parse out the three ID strings from the message link
            m = re.search('/(\d+)/(\d+)/(\d+)', user_message)
            if not m:
                return "I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel."
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return "I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again."
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                return "It seems this channel was deleted or never existed. Please try again or say `cancel` to cancel."

            # Fetch actual message from channel
            try:
                new_message = await channel.fetch_message(int(m.group(3)))
                params['logs'].append(new_message)
            except discord.errors.NotFound:
                return "It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."

            reply = "Received this message:```" + new_message.author.name + ": " + new_message.content + "```\n"
            reply += "Please continuously copy paste the link to the messages in your chat history that you want to report.\n"
            reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`.\n"
            reply += "When you are done, please enter `Complete` to indicate so."
        elif req_to_block == "":
            reply = "Thank you for filling out this report! We have finalized the reporting process and will notify our moderation team shortly.\n"
            reply += "For now, please indicate whether or not you would like the reported user blocked. \n"
            reply += "- Blocked users will not be notified that they are blocked and you will no longer receive any communications from them.\n\n"
            reply += "Please reply with `YES` or `NO` below:\n"
            
            # Update parameter to new type to continue
            params["completed"]
            params["req_to_block"] = -1
        elif req_to_block == -1:
            # Update req_to_block param based on user_message
            if user_message == "yes":
                params["req_to_block"] = True
            elif user_message == "no":
                params["req_to_block"] = False
            else:
                return "Please reply with `YES` or `NO` below:"

            reply = "Thank you for your time, have a great rest of your day!"
            params["completed"] = True
        
        else:
            # Should never get here
            reply = "Soliciation Report Complete."
            params["completed"] = True
        
        return reply
    
    async def impersonation_flow(self, user_message : str, params : dict):
        """
        This function handles the Solicitation flow specifically, for better code visibility in the main handler function.
        """
        action = params['action']
        has_shared_logs = params['has_shared_logs']
        req_to_block = params['req_to_block']
        params['completed'] = False
        is_complete = params['completed']

        reply = ""

        if action is None:
            reply = "Please indicate what method of impersonation is perpetrated in the reported message:\n\n"
            reply += "**1.) Celebrity**\n"
            reply += "    - The person is pretending to be a celebrity in order to get your confidence\n\n"
            reply += "**2.) Government Authority**\n"
            reply += "    - The person is predending to be a Government Authority in order to say that they have authrority over you .\n\n"
            reply += "**3.) Other User**\n"
            reply += "    - The person is pretending to be another user in order to get your confidence .\n"

            # Update action state to empty string, while waiting for response
            params['action'] = ""
        
        elif has_shared_logs is None:

            # Regex to extract numbers in message content and update params
            temp = re.findall(r'\d+', user_message)
            options = list(map(int, temp))
            for option in options:
                text = ""
                if option == 1:
                    text = "Impersonating: Celebrity,\n"
                elif option == 2:
                    text = "Impersonating: Governemt Oficcial,\n"
                elif option == 3:
                    text = "Impersonating: Other user\n"
                else:
                    continue

                params["action"] += text

            reply = "Please indicate whether or not you would like to include your chat history in this report.\n"
            reply += "Please reply with `YES` or `NO` below:"
            
            # Update parameter to non-None type to continue
            params["has_shared_logs"] = ""
            has_shared_logs = params["has_shared_logs"]

        elif req_to_block is  None:
            print("user_message: ", user_message)
            
            # Update has_shared_logs param based on user_message
            if user_message == "yes":
                params["has_shared_logs"] = True
            elif user_message == "no":
                params["has_shared_logs"] = False
            else:
                return "Please reply with `YES` or `NO` below:"
            
            params['logs'] = []
            
            if params["has_shared_logs"]:
                reply = "Please continuously copy paste the link to the messages in your chat history that you want to report.\n"
                reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`.\n"
                reply += "When you are done, please enter `Complete` to indicate so."
            else:
                reply = "Please enter `Complete` to confirm no additional messages."
            
            params['req_to_block'] = ""
        elif params['logs'] is not None and user_message != 'complete' and req_to_block == "":
            # Parse out the three ID strings from the message link
            m = re.search('/(\d+)/(\d+)/(\d+)', user_message)
            if not m:
                return "I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel."
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return "I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again."
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                return "It seems this channel was deleted or never existed. Please try again or say `cancel` to cancel."

            # Fetch actual message from channel
            try:
                new_message = await channel.fetch_message(int(m.group(3)))
                params['logs'].append(new_message)
            except discord.errors.NotFound:
                return "It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."

            reply = "Received this message:```" + new_message.author.name + ": " + new_message.content + "```\n"
            reply += "Please continuously copy paste the link to the messages in your chat history that you want to report.\n"
            reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`.\n"
            reply += "When you are done, please enter `Complete` to indicate so."
        elif req_to_block == "":
            reply = "Thank you for filling out this report! We have finalized the reporting process and will notify our moderation team shortly.\n"
            reply += "For now, please indicate whether or not you would like the reported user blocked. \n"
            reply += "- Blocked users will not be notified that they are blocked and you will no longer receive any communications from them.\n\n"
            reply += "Please reply with `YES` or `NO` below:\n"
            
            # Update parameter to new type to continue
            params["completed"]
            params["req_to_block"] = -1
        elif req_to_block == -1:
            # Update req_to_block param based on user_message
            if user_message == "yes":
                params["req_to_block"] = True
            elif user_message == "no":
                params["req_to_block"] = False
            else:
                return "Please reply with `YES` or `NO` below:"

            reply = "Thank you for your time, have a great rest of your day!"
            params["completed"] = True
        
        else:
            # Should never get here
            reply = "Soliciation Report Complete."
            params["completed"] = True
        
        return reply