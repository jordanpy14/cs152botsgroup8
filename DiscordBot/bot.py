"""
Team 8
Colette Do
Carlo Dino
Christian Gebhardt
Euysun Hwang
Jordan Paredes
"""

# bot.py
import discord
from discord.ext import commands
import os
import json
import logging
import re
import requests
from report import Report
import pdb
from openai import OpenAI
from collections import defaultdict
from enum import Enum, auto
import datetime
import json


    

# Set up logging to the console
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# There should be a file called 'tokens.json' inside the same folder as this file
token_path = 'tokens.json'
if not os.path.isfile(token_path):
    raise Exception(f"{token_path} not found!")
with open(token_path) as f:
    # If you get an error here, it means your token is formatted incorrectly. Did you put it in quotes?
    tokens = json.load(f)
    discord_token = tokens['discord']
    openai_token = tokens['openAI']
    openai_org = tokens['openAIorg']

OpenAIclient = OpenAI(api_key=openai_token, organization=openai_org)

class ModeratorStep(Enum):
    NO_STATE = auto()
    REPORT_STATE = auto()
    MOD_START = auto()
    CHOOSE_PRIORITY = auto()
    CHOOSE_REPORT = auto()
    RANK_SEVERITY = auto()
    DEAL_WITH_SEVERITY_RANK = auto()
    FALSE_REPORT = auto()
    COMPLETE = auto()

class moderator:
    def __init__(self):
        self.state = ModeratorStep.NO_STATE
        self.priority = None
        self.priority_choice = None
        self.report = None
        self.severity_rank = None
        self.false_report = None
        
class ModBot(discord.Client):
    CANCEL_KEYWORD = "cancel"
    
    def __init__(self): 
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='.', intents=intents)
        self.group_num = None
        self.mod_channels = {} # Map from guild to the mod channel id for that guild
        self.reports = {} # Map from user IDs to the state of their report
        self.load_report_history() # dic of UserID, to dic to report history, to count of reports
        self.load_queue()
        self.load_false_user_reports()
        self.load_false_bot_reports()
        self.moderators = [430869490453184522, 249676214724198412] # so far only Jordan and Carlo
        self.moderator_state = {}
        self.moderator_priority = {}
        self.moderator_priority_choice = {}
        self.moderator_severity_rank = {}
        with open('dataset/scam_links.json', 'r') as file:
            scam_links = json.load(file)
            self.scam_links = scam_links['links']
    
    """
    Initialize, save, and load methods for JSON files.
    """
    def check_links(self, message):
        for link in self.scam_links:
            if link['url'] in message:
                return True
        return False

    ### User Reports ###
    def load_false_user_reports(self):
        try:
            with open("false_user_reports.json", "r") as file:
                self.false_reports = json.load(file)
        except FileNotFoundError:
            self.false_reports = {}
            self.save_false_user_reports()
            
    def save_false_user_reports(self):
        with open("false_user_reports.json", "w") as file:
            json.dump(self.false_reports, file, indent=4)
            
    def update_false_user_reports(self, user_id, user_report):
        if user_id not in self.false_reports.keys():
            self.false_reports[user_id] = {'count': 0}
            self.false_reports[user_id]['user_report'] = []
            
        self.false_reports[user_id]['user_report'].append(user_report)
        self.false_reports[user_id]['count'] += 1
        self.save_false_bot_reports()
    
    ### Automated GPT Reports ###
    def load_false_bot_reports(self):
        try:
            with open("false_bot_reports.json", "r") as file:
                self.false_bot_reports = json.load(file)
        except FileNotFoundError:
            self.false_bot_reports = []
            self.save_false_bot_reports()

    def save_false_bot_reports(self):
        with open("false_bot_reports.json", "w") as file:
            json.dump(self.false_bot_reports, file, indent=4)

    def update_false_bot_reports(self, report):
        self.false_bot_reports.append(report)
        self.save_false_bot_reports()
        
    ### Queue ###
    def load_queue(self):
        try:
            with open("queue.json", "r") as file:
                self.queue = json.load(file)
        except FileNotFoundError:
            # Initialize three queues: low, medium, and high priority
            self.queue = {"LOW": [], "MEDIUM": [], "HIGH": []}
        self.save_queue()

    def save_queue(self):
        with open("queue.json", "w") as file:
            json.dump(self.queue, file, indent=4)
            
    def update_queue(self, user_id, message_id, classification, priority, message, user_report=None):
        current_qeue = self.queue[priority]
        
        # already_in_queue = any([report['message_id'] == message_id for report in current_qeue])
        
        # if already_in_queue:
        #     return
        message_details = {
            'id': message.id,
            'content': message.content,
            'author_id': message.author.id,
            'channel_id': message.channel.id
        }
        self.queue[priority].append({'user_id': user_id, 'message_id': message_id, 'classification': classification, 'message': message_details, 'user_report': user_report, 'contains_harmful_link': self.check_links(message.content)})
        self.save_queue()
    
    # Report History
    def load_report_history(self):
        try:
            with open("report_history.json", "r") as file:
                self.report_history = json.load(file)
        except FileNotFoundError:
            self.report_history = {}
            self.save_report_history()
            
    def save_report_history(self):
        with open("report_history.json", "w") as file:
            json.dump(self.report_history, file, indent=4)
            
    def update_report_history(self, user_id, message_id, classification, priority, message, user_report=None):
        print("updating report history")
        user_id = str(user_id)
        message_id = str(message_id)
        if user_id not in self.report_history.keys():
            self.report_history[user_id] = {}

        if message_id not in self.report_history[user_id]:
            self.report_history[user_id][message_id] = {'count': 0, 'priority': None}
                
        message_details = {
            'id': message.id,
            'content': message.content,
            'author_id': message.author.id,
            'channel_id': message.channel.id
        }

        print("user id", user_id)
        # Increment count and update priority
        self.report_history[user_id][message_id]['count'] += 1
        self.report_history[user_id][message_id]['date'] = datetime.datetime.now().isoformat()
        self.report_history[user_id][message_id]['priority'] = priority
        self.report_history[user_id][message_id]['classification'] = classification
        self.report_history[user_id][message_id]['message'] = message_details
        self.report_history[user_id][message_id]['contains_harmful_link'] = self.check_links(message.content)
        if 'user_report' not in self.report_history[user_id][message_id] or not self.report_history[user_id][message_id]['user_report']:
            self.report_history[user_id][message_id]['user_report'] = []
            
        if user_report: self.report_history[user_id][message_id]['user_report'].append(user_report)

        self.save_report_history()
        
    def prepare_report_for_json(self, report):
        
        if isinstance(report.get('params'), defaultdict):
            report['params'] = dict(report['params'])  

        return report

    """
    Bot Methods
    """
    async def on_ready(self):
        print(f'{self.user.name} has connected to Discord! It is these guilds:')
        for guild in self.guilds:
            print(f' - {guild.name}')
        print('Press Ctrl-C to quit.')

        # Parse the group number out of the bot's name
        match = re.search('[gG]roup (\d+) [bB]ot', self.user.name)
        if match:
            self.group_num = match.group(1)
        else:
            raise Exception("Group number not found in bot's name. Name format should be \"Group # Bot\".")

        # Find the mod channel in each guild that this bot should report to
        for guild in self.guilds:
            for channel in guild.text_channels:
                if channel.name == f'group-{self.group_num}-mod':
                    self.mod_channels[guild.id] = channel


    async def on_message(self, message):
        '''
        This function is called whenever a message is sent in a channel that the bot can see (including DMs). 
        Currently the bot is configured to only handle messages that are sent over DMs or in your group's "group-#" channel. 
        '''
        # Ignore messages from the bot 
        if message.author.id == self.user.id:
            return
        # Check if this message was sent in a server ("guild") or if it's a DM
        if message.guild:
            if message.channel.name == f'group-{self.group_num}':
                await self.handle_channel_message(message)
            elif message.channel.name == f'group-{self.group_num}-mod':
                await self.handle_mod_channel_message(message)
        else:
            # Need to transition DM features into main-mod channels.
            await self.handle_dm(message)

        if not message.channel.name == f'group-{self.group_num}':
            return


    def clear_moderator(self ,message,  moderator):
        '''
        Clear a moderator from the system.
        '''
        self.moderator_state.pop(moderator.id, None)
        self.moderator_priority_choice.pop(moderator.id, None)
        self.moderator_priority.pop(message.author.id, None)
        self.moderator_severity_rank.pop(message.author.id, None)

    """
    Handler Methods
    """

    ### Handle DM Flow Method ###
    async def handle_dm(self, message):
        """
        Original functionality of handle_dm was to report and moderate, however this needs to be transitioned
        to the main chat / mod chats respectively for Milestone 3. This method will let the bot to only handle
        help messages, and tell the user to write reports / moderate reports on group-8 channels.
        """
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply =  "Use the `report` command to begin the reporting process.\n"
            reply += "Use the `cancel` command to cancel the report or moderation process.\n"
            reply += "Use the `moderate` command if you are a moderator and want to go through the messages that were flagged.\n"
            reply += "\nYou may initiate a report or moderation session in the main channel / mod channel, respectively."
            await message.channel.send(reply)
            return
              

    async def handle_moderation(self, message, moderator):
        content = message.content.lower().strip()
        channel = message.channel
        print(f"Current state: {self.moderator_state.get(moderator.id)}")
        print(f"Message content: '{content}'")

        if self.moderator_state.get(moderator.id) == ModeratorStep.NO_STATE:
            print("choose priority, ", content)
            # Prompt moderator to choose a priority level
            await channel.send("Please choose a priority number you want to review: 1) LOW, 2) MEDIUM, 3) HIGH")
            low_count = len(self.queue['LOW'])
            mid_count = len(self.queue['MEDIUM'])
            high_count = len(self.queue['HIGH'])
            await channel.send(f"Number of reports in each priority level: LOW: {low_count}, MEDIUM: {mid_count}, HIGH: {high_count}")
            self.moderator_state[moderator.id] = ModeratorStep.CHOOSE_PRIORITY
            return

        elif self.moderator_state[moderator.id] == ModeratorStep.CHOOSE_PRIORITY:
            try:
                print("choose priority: ", content)
                priority_index = int(content)
                priorities = {1: 'LOW', 2: 'MEDIUM', 3: 'HIGH'}
                if priority_index in priorities:
                    priority = priorities[priority_index]
                    self.moderator_priority[moderator.id] = priority
                    await self.list_reports_by_priority(moderator, priority, channel)
                else:
                    await channel.send("Invalid priority. Please choose from: 1) LOW, 2) MEDIUM, 3) HIGH")
            except ValueError:
                await channel.send("Please enter a number corresponding to the priority: 1, 2, or 3.")
                self.moderator_state[moderator.id] = ModeratorStep.CHOOSE_PRIORITY
            return
        elif self.moderator_state[moderator.id] == ModeratorStep.CHOOSE_REPORT:
            try:
                print("choose report: ", content)
                report_index = int(content)
                self.moderator_priority_choice[moderator.id] = report_index
                await self.show_detailed_report(moderator, report_index, channel)
            except ValueError:
                await channel.send("Please enter a number corresponding to the report you want to view.")
                self.moderator_state[moderator.id] = ModeratorStep.CHOOSE_PRIORITY
            return
        elif self.moderator_state[moderator.id] == ModeratorStep.RANK_SEVERITY:
            try:
                print("rank severity: ", content)
                severity_index = int(content)
                self.moderator_severity_rank[moderator.id] = severity_index
                await self.rank_severity(moderator, severity_index, channel)
            except ValueError:
                await channel.send("Please enter a number corresponding to the severity level you want to assign.")
                self.moderator_state[moderator.id] = ModeratorStep.RANK_SEVERITY
            return
        elif self.moderator_state[moderator.id] == ModeratorStep.DEAL_WITH_SEVERITY_RANK:
            if self.moderator_severity_rank[moderator.id] == 1:
                if content == "yes":
                    report = self.queue[self.moderator_priority[moderator.id]][self.moderator_priority_choice[moderator.id]]['user_report']
                    number_of_false_reports = 0
                    if report['reporter'] in self.false_reports:
                        number_of_false_reports = len(self.false_reports[report['reporter']])
                    await channel.send(f"Was this a first offense? If so, please respond with `yes` or `no`.\n The number of false reports that user has right now: {number_of_false_reports}")
                    self.update_false_user_reports(report['reporter'], report)
                    self.moderator_state[moderator.id] = ModeratorStep.FALSE_REPORT
                elif content == "no":
                    await channel.send("There will be no system action and the report will be closed.")
                    self.moderator_state[moderator.id] = ModeratorStep.COMPLETE
                else:
                    await channel.send("Please respond with `yes` or `no`.")
            elif self.moderator_severity_rank[moderator.id] == 4:
                if content == "yes":
                    await channel.send("The authorities will be contacted and the user will be kicked, and the report will be sent to law enforcemnt, and message will be deleted.\n Enter 'y' to close report")
                    self.moderator_state[moderator.id] = ModeratorStep.COMPLETE
                elif content == "no":
                    await channel.send("The authorities will not be contacted, but the user will be kicked and message will be deleted.\n Enter 'y' to close report")
                    self.moderator_state[moderator.id] = ModeratorStep.COMPLETE
                else:
                    await channel.send("Please respond with `yes` or `no`.")
                    self.moderator_state[moderator.id] = ModeratorStep.DEAL_WITH_SEVERITY_RANK
        elif self.moderator_state[moderator.id] == ModeratorStep.FALSE_REPORT:
            if content == "yes":
                await channel.send("The account will be shut down for repeated abuse of report system. \n Enter 'y' to close report")
                self.moderator_state[moderator.id] = ModeratorStep.COMPLETE
            elif content == "no":
                await channel.send("The report will be closed and the user will be warned. \n Enter 'y' to close report")
                self.moderator_state[moderator.id] = ModeratorStep.COMPLETE
            else:
                await channel.send("Please respond with `yes` or `no`.")
                self.moderator_state[moderator.id] = ModeratorStep.FALSE_REPORT
        elif self.moderator_state[moderator.id] == ModeratorStep.COMPLETE:
            self.queue[self.moderator_priority[moderator.id]].pop(self.moderator_priority_choice[moderator.id])
            self.save_queue()
            self.clear_moderator(message, moderator)
            await channel.send("Moderation session ended.")
            return
            
    async def list_reports_by_priority(self, moderator, priority, channel):
        reports = self.queue[priority]
        if reports:
            response = f"Please choose a report index you want to moderate\n"
            response += f"Reports with priority {priority}:\n"
            for idx, report in enumerate(reports, 0):
                response += f"Index: {idx}.\nReport ID: {report['message_id']},\nContent: {report['message']['content']},\nClassification: {report['classification']}\n\n\n"
            await channel.send(response)
            self.moderator_state[moderator.id] = ModeratorStep.CHOOSE_REPORT
        else:
            await channel.send(f"No reports currently require moderation at the {priority} level. Please choose another priority.")
            self.moderator_state[moderator.id] = ModeratorStep.CHOOSE_PRIORITY
            self.moderator_priority.pop(moderator.id)


    async def show_detailed_report(self, moderator, index, channel):
        try:
            priority = self.moderator_priority[moderator.id]
            reports = self.queue[priority]
            report = reports[index]
            historyReport = self.report_history[str(report['user_id'])][str(report['message_id'])] 
            userReports = historyReport['user_report']
            response = f"Please rank the severity of the report: \n"
            response += f"1) False Report \n"
            response += f"2) Mild Severity which leads to deleting message and warning offending user \n"
            response += f"3) Moderate Severity which leads to deleting message and kicking offending user \n"
            response += f"4) High Severity which leads to deleting message and banning offending user and possible law enforcement\n"
            response += f"Detail Report:\n"
            response += f"How many times the message was reported: {historyReport['count']}\n"
            response += f"Initial Report: {historyReport['date']}\n"
            response += f"Classification: {historyReport['classification']}\n"
            response += f"Message Content: {historyReport['message']['content']}\n"
            
            for idx, user_report in enumerate(userReports, 0):
                response += f"User Report {idx}: {user_report}\n"
                
            await channel.send(response)
            self.moderator_state[moderator.id] = ModeratorStep.RANK_SEVERITY
        except IndexError:
            await channel.send("Your input was out of range. Please enter a valid report number.")
            self.moderator_state[moderator.id] = ModeratorStep.CHOOSE_REPORT
            self.moderator_priority_choice.pop(moderator.id)
        except Exception as e:
            await channel.send(f"An error occurred: {str(e)}")
            logging.error(f"Failed to display detailed report: {str(e)}")
            self.moderator_state[moderator.id] = ModeratorStep.CHOOSE_REPORT
            self.moderator_priority_choice.pop(moderator.id)
            
    async def rank_severity(self, moderator, severity_index, channel):
        try:
            current_ticket = self.queue[self.moderator_priority[moderator.id]][self.moderator_priority_choice[moderator.id]]
            if severity_index in range(1, 5):
               if severity_index == 1:
                    if not current_ticket['user_report']:
                       await channel.send("No user created this ticket. The report will be closed. Ticket will be used to track false reports and train better model\n Enter 'y' to close report")
                       self.update_false_bot_reports(current_ticket)
                       self.moderator_state[moderator.id] = ModeratorStep.COMPLETE
                       return
                    else:
                        await channel.send("Was this a false report? If so, please respond with `yes` or `no`.")
                        self.moderator_state[moderator.id] = ModeratorStep.DEAL_WITH_SEVERITY_RANK
                        return
               elif severity_index == 2:
                   await channel.send("Deleted the message and warned the offending user. \n Enter 'y' to close report")
                   self.moderator_state[moderator.id] = ModeratorStep.COMPLETE
                   return
               elif severity_index == 3:
                    await channel.send("Deleted the message and kicked the offending user.\n Enter 'y' to close report")
                    self.moderator_state[moderator.id] = ModeratorStep.COMPLETE
                    return
               elif severity_index == 4:
                    await channel.send("Does this message require legal action as well as contacting authoritie?\n Please respond with `yes` or `no`.")
                    self.moderator_state[moderator.id] = ModeratorStep.DEAL_WITH_SEVERITY_RANK
                    return
            else:
                await channel.send("Invalid severity level. Please enter a number from 1 to 4.")  
                self.moderator_state[moderator.id] = ModeratorStep.RANK_SEVERITY
        except IndexError:
            await channel.send("Your input was out of range. Please enter a valid severity level.")
            self.moderator_state[moderator.id] = ModeratorStep.RANK_SEVERITY
            self.moderator_severity_rank.pop(moderator.id)
        except Exception as e:
            await channel.send(f"An error occurred: {str(e)}")
            logging.error(f"Failed to rank severity: {str(e)}")
            self.moderator_state[moderator.id] = ModeratorStep.RANK_SEVERITY
            self.moderator_severity_rank.pop(moderator.id)

        
    async def handle_mod_channel_message(self, message):
        # Only handle messages sent in the "group-#" channel
        if not message.channel.name == f'group-{self.group_num}-mod':
            return
        
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply =  "Use the `report` command to begin the reporting process.\n"
            reply += "Use the `cancel` command to cancel the report or moderation process.\n"
            reply += "Use the `moderate` command if you are a moderator and want to go through the messages that were flagged.\n"
            reply += "\nYou may initiate a report or moderation session in the main channel / mod channel, respectively."
            await message.channel.send(reply)
            return
        
        # Cancel an ongoing moderation session
        user_message = str.lower(str(message.content))
        if user_message.startswith(self.CANCEL_KEYWORD) and message.author.id in self.moderator_state:
            self.clear_moderator(message, message.author)
            await message.channel.send("Cancellation confirmed. Moderation session ended.")
            return

        # Handle Moderation Flow
        if message.content.startswith('moderate') or message.author.id in self.moderator_state:
            if message.author.id in self.moderators:
                if message.author.id not in self.moderator_state:
                    self.moderator_state[message.author.id] = ModeratorStep.NO_STATE
                await self.handle_moderation(message, message.author)
            else :
                await message.channel.send("You do not have permission to perform moderation tasks.")
            return

    async def handle_channel_message(self, message):
        # Only handle messages sent in the "group-#" channel
        if not message.channel.name == f'group-{self.group_num}':
            return
        
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply =  "Use the `report` command to begin the reporting process.\n"
            reply += "Use the `cancel` command to cancel the report or moderation process.\n"
            reply += "Use the `moderate` command if you are a moderator and want to go through the messages that were flagged.\n"
            reply += "\nYou may initiate a report or moderation session in the main channel / mod channel, respectively."
            await message.channel.send(reply)
            return
        
        ### Automatic Reporting Flow ###
        if message.content != Report.START_KEYWORD and not message.author in self.reports:
            # We will pre-scan all new messages that aren't bot commands or reporting responses
            classification = await self.eval_text(message)

            # If we have a classification, notify mod chat (eval_text automatically adds to queue)
            if classification:
                msg_type, priority = classification
                await mod_channel.send(f'Forwarded message:\n{message.author.name}: "{message.content}" \n{self.code_format("Classification: " + msg_type + " Priority: " + priority)}')
            return

        ### Reporting Flow ###
        author_id = message.author.id
        responses = []

        # Only respond to messages if they're part of a reporting flow
        if author_id not in self.reports and not message.content.startswith(Report.START_KEYWORD):
            return

        # If we don't currently have an active report for this user, add one
        if author_id not in self.reports:
            self.reports[author_id] = Report(self)

        # Let the report class handle this message; forward all the messages it returns to us
        responses = await self.reports[author_id].handle_message(message)
        for r in responses:
            if r:
                await message.channel.send(r)
            else:
                logger.error("Attempted to send an empty message.")  # Log the error for debugging
                await message.channel.send("An error occurred, please try again.")  # Send a generic error message to the user

        # If the report is complete or cancelled, remove it from our map AND add to queue
        if self.reports[author_id].report_complete():
            if not self.reports[author_id].report_cancelled:
                mod_channel = self.mod_channels[message.guild.id]

                print("message being sent:", self.reports[author_id].message.content)
                result = await self.eval_text(self.reports[author_id].message, self.prepare_report_for_json(self.reports[author_id].report))
                if result:
                  msg_type, priority = result
                  print("Class:", msg_type, "Priority:", priority)

                # way to still add to queue incase gpt fails 
                # if not result or result == "Error during classification, GPT-3.5 did not return a valid classification and priority." or result == None:
                #     self.update_queue(author_id, self.reports[author_id].message.id, "NONE", "MEDIUM", self.reports[author_id].message, self.prepare_report_for_json(self.reports[author_id].report))
            self.reports.pop(author_id)

        # Forward the message to the mod channel
        
        classification = await self.eval_text(message)

        if classification:
            msg_type, priority = classification
            await mod_channel.send(f'Forwarded message:\n{message.author.name}: "{message.content}" \n{self.code_format("Classification: " + msg_type + " Priority: " + priority)}')


    async def eval_text(self, message, report=None):
        '''
        Evaluate the text using OpenAI's GPT-3.5 model to classify it as either Fraud, Impersonation,
        Violence, Harmful Behavior, Just uncomfortable, or unclassified.
        '''
        try:
            completion = OpenAIclient.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are assisting in classifying messages. Categories: Fraud, Impersonation, Violence, Harmful Behavior, Uncomfortable. "},
                    {"role": "system", "content": "Classify it as `Unsure` if it doesn't fit any of the categories but you think it should still be flagged Make sure that you only give back one category please."},
                    {"role": "system", "content": "If the messsage is not harmful, please classify it as `NONE`"},
                    {"role": "system", "content": "Also give me a priority of LOW, MEDIUM, or HIGH. If you are unsure, please give a priority of LOW."},
                    {"role": "system", "content": "If the messsage is not harmful, please give a priority as `NONE`"},
                    {"role": "system", "content": "If the message is Fraud and it is asking someone to move to a different platform please give a priority of LOW"},
                    {"role": "system", "content": "Please only give the answer in the following format: `Category: <category>, Priority: <priority>`. For example: `Category: Fraud, Priority: HIGH`."},
                    {"role": "system", "content": "All other formats will be invalid and crash, it is imperative that this format is maintained and no other text is included and the spacing is accurate."},
                    {"role": "system", "content": "Please classify the following message:"},
                    {"role": "user", "content": "\"\"" + message.content + "\"\""}
                ],
                model="gpt-3.5-turbo"
            )
            answer = completion.choices[0].message.content
            ## making sure that the answer is in the correct format
            if "Category: " in answer and "Priority: " in answer:
                classification = answer.split("Category: ")[1].split(",")[0].strip()
                priority = answer.split("Priority: ")[1].strip()
                if classification == "Fraud" or classification == "Impersonation" or classification == "Violence" or classification == "Harmful Behavior" or classification == "Uncomfortable" or classification == "Unsure" or classification == "NONE":
                    if priority == "LOW" or priority == "MEDIUM" or priority == "HIGH" or priority == "NONE":
                        if classification == "NONE" and priority != "NONE":
                            priority = "NONE"
                        elif classification != "NONE" and priority == "NONE":
                            classification = "NONE"
                        elif classification == "Uncomfortable":
                            priority = "MEDIUM"  
                        elif classification != "NONE" or report:
                            if report:
                                classification = report['type']
                            self.update_report_history(message.author.id, message.id, classification, priority, message, report)
                            self.update_queue(message.author.id, message.id, classification, priority, message, report)
                        #return f"Classification: {classification}, Priority: {priority}" 
                        return (classification, priority)
            else:
                # Error during classficiation, GPT did not return a valid Classification - Priority response.
                return             
        except Exception as e:
            logger.error(f"Failed to classify message with OpenAI: {str(e)}")
            return 


    def code_format(self, text):
        ''''
        TODO: Once you know how you want to show that a message has been 
        evaluated, insert your code here for formatting the string to be 
        shown in the mod channel. 
        '''
        return  text


client = ModBot()
client.run(discord_token)