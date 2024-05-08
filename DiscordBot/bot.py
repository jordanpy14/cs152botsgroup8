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

class ModBot(discord.Client):
    def __init__(self): 
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='.', intents=intents)
        self.group_num = None
        self.mod_channels = {} # Map from guild to the mod channel id for that guild
        self.reports = {} # Map from user IDs to the state of their report
        self.load_report_history() # dic of UserID, to dic to report history, to count of reports
        self.load_queue()
        
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
        message_details = {
            'id': message.id,
            'content': message.content,
            'author_id': message.author.id,
            'channel_id': message.channel.id
        }
        self.queue[priority].append({'user_id': user_id, 'message_id': message_id, 'classification': classification, 'message': message_details, 'user_report': user_report})
        self.save_queue()
            
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
        if user_id not in self.report_history:
            self.report_history[user_id] = {}

        if message_id not in self.report_history[user_id]:
            self.report_history[user_id][message_id] = {'count': 0, 'priority': None}
            
        message_details = {
            'id': message.id,
            'content': message.content,
            'author_id': message.author.id,
            'channel_id': message.channel.id
        }

        # Increment count and update priority
        self.report_history[user_id][message_id]['count'] += 1
        self.report_history[user_id][message_id]['priority'] = priority
        self.report_history[user_id][message_id]['classification'] = classification
        self.report_history[user_id][message_id]['message'] = message_details
        self.report_history[user_id][message_id]['user_report'] = user_report

        self.save_report_history()
        
    def prepare_report_for_json(self, report):
        
        if isinstance(report.get('params'), defaultdict):
            report['params'] = dict(report['params'])  

        return report

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
            await self.handle_channel_message(message)
        else:
            await self.handle_dm(message)

    async def handle_dm(self, message):
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply =  "Use the `report` command to begin the reporting process.\n"
            reply += "Use the `cancel` command to cancel the report process.\n"
            await message.channel.send(reply)
            return

        author_id = message.author.id
        responses = []

        # Only respond to messages if they're part of a reporting flow
        if author_id not in self.reports and not message.content.startswith(Report.START_KEYWORD):
            return

        # If we don't currently have an active report for this user, add one
        if author_id not in self.reports:
            self.reports[author_id] = Report(self)

        # Let the report class handle this message; forward all the messages it returns to uss
        responses = await self.reports[author_id].handle_message(message)
        for r in responses:
            await message.channel.send(r)

        # If the report is complete or cancelled, remove it from our map
        if self.reports[author_id].report_complete():
            await self.eval_text(self.reports[author_id].message, self.prepare_report_for_json(self.reports[author_id].report))
            self.reports.pop(author_id)

    async def handle_mod_channel_message(self, message):
        # Only handle messages sent in the "group-#" channel
        if not message.channel.name == f'group-{self.group_num}-mod':
            return
        
        author_id = message.author.id
        if author_id in self.moderation_actions or message.content.startswith(Report.MOD_KEYWORD):
            await self.handle_mod_flow(message)
            return

    async def handle_channel_message(self, message):
        # Only handle messages sent in the "group-#" channel
        if not message.channel.name == f'group-{self.group_num}':
            return

        # Forward the message to the mod channel
        mod_channel = self.mod_channels[message.guild.id]
        # await mod_channel.send(f'Forwarded message:\n{message.author.name}: "{message.content}"')
        classification = await self.eval_text(message)
        await mod_channel.send(f'Forwarded message:\n{message.author.name}: "{message.content}" \n{self.code_format(classification)}')


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
                    {"role": "system", "content": "Give the answer in the format: `Category: <category>, Priority: <priority>`. For example: `Category: Fraud, Priority: HIGH`."},
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
                        if classification != "NONE" and priority == "NONE":
                            classification = "NONE"  
                        if classification != "NONE" and priority != "NONE":
                            self.update_report_history(message.author.id, message.id, classification, priority, message, report)
                            self.update_queue(message.author.id, message.id, classification, priority, message, report)
                        return f"Classification: {classification}, Priority: {priority}" 
            else:
                return "Error during classification, GPT-3.5 did not return a valid classification and priority."                 
        except Exception as e:
            logger.error(f"Failed to classify message with OpenAI: {str(e)}")
            return "Error during classification"


    def code_format(self, text):
        ''''
        TODO: Once you know how you want to show that a message has been 
        evaluated, insert your code here for formatting the string to be 
        shown in the mod channel. 
        '''
        return  text


client = ModBot()
client.run(discord_token)