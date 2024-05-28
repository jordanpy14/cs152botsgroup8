import json
# from DiscordBot.bot import OpenAIclient
    
    

if __name__ == '__main__':
    with open('dataset/scam_links.json', 'r') as file:
        scam_links = json.load(file)
        scam_links = scam_links['links']
        
    def check_links( message):
        for link in scam_links:
            if link['url'] in message:
                return True
        return False
    
    print("Checking links: True", check_links("Dear User,\\n\\nWe have detected unusual activity on your CryptoExchange account. For your security, please verify your account immediately by clicking the link below: [http://test.false] Thank you for your cooperation,\\n\\nCryptoExchange Security Team"))    
    print("Checking links: http://myethwallet.net", check_links("http://myethwallet.net"))  
    print("Checking links: http://test.com", check_links("http://test.com"))  
    # with open('dataset.json', 'r') as file:
    #     data = json.load(file)
    # # Iterate through each message and classify
    # for message in data['messages']:
    #     content = message['content']
    #     label = message['label']
    #     if label in categories:
    #         category = categories[label]
    #         priority = determine_priority(category)
    #     else:
    #         category = "Unsure"
    #         priority = "LOW"
            
    #     # Here you should include the logic to call the OpenAI model to get more refined classification
    #     # Since you mentioned crashing, let's assume the format is strictly enforced as required
    #     try:
    #         response = OpenAIclient.chat.completions.create(
    #             messages=[
    #                 {"role": "system", "content": "You are assisting in classifying messages. Categories: Fraud, Impersonation, Violence, Harmful Behavior, Uncomfortable."},
    #                 {"role": "system", "content": "Classify it as `Unsure` if it doesn't fit any of the categories but you think it should still be flagged. Make sure that you only give back one category please."},
    #                 {"role": "user", "content": content}
    #             ],
    #             model="gpt-3.5-turbo"
    #         )
    #         # Parse response
    #         completion = response.choices[0].text.strip()
    #         print(f"Message: {content}")
    #         print(f"Classification: {completion}")
    #     except Exception as e:
    #         print(f"Error processing message: {str(e)}")
            
    # try:
    #         completion = OpenAIclient.chat.completions.create(
    #             messages=[
    #                 {"role": "system", "content": "You are assisting in classifying messages. Categories: Fraud, Impersonation, Violence, Harmful Behavior, Uncomfortable. "},
    #                 {"role": "system", "content": "Classify it as `Unsure` if it doesn't fit any of the categories but you think it should still be flagged Make sure that you only give back one category please."},
    #                 {"role": "system", "content": "If the messsage is not harmful, please classify it as `NONE`"},
    #                 {"role": "system", "content": "Also give me a priority of LOW, MEDIUM, or HIGH. If you are unsure, please give a priority of LOW."},
    #                 {"role": "system", "content": "If the messsage is not harmful, please give a priority as `NONE`"},
    #                 {"role": "system", "content": "If the message is Fraud and it is asking someone to move to a different platform please give a priority of LOW"},
    #                 {"role": "system", "content": "Please only give the answer in the following format: `Category: <category>, Priority: <priority>`. For example: `Category: Fraud, Priority: HIGH`."},
    #                 {"role": "system", "content": "All other formats will be invalid and crash, it is imperative that this format is maintained and no other text is included and the spacing is accurate."},
    #                 {"role": "system", "content": "Please classify the following message:"},
    #                 {"role": "user", "content": "\"\"" + message.content + "\"\""}
    #             ],
    #             model="gpt-3.5-turbo"
    #         )
    #         answer = completion.choices[0].message.content
    #         ## making sure that the answer is in the correct format
    #         if "Category: " in answer and "Priority: " in answer:
    #             classification = answer.split("Category: ")[1].split(",")[0].strip()
    #             priority = answer.split("Priority: ")[1].strip()
    #             if classification == "Fraud" or classification == "Impersonation" or classification == "Violence" or classification == "Harmful Behavior" or classification == "Uncomfortable" or classification == "Unsure" or classification == "NONE":
    #                 if priority == "LOW" or priority == "MEDIUM" or priority == "HIGH" or priority == "NONE":
    #                     if classification == "NONE" and priority != "NONE":
    #                         priority = "NONE"
    #                     elif classification != "NONE" and priority == "NONE":
    #                         classification = "NONE"
    #                     elif classification == "Uncomfortable":
    #                         priority = "MEDIUM"  
    #                     elif classification != "NONE" or report:
    #                         if report:
    #                             classification = report['type']
    #                     return (classification, priority)
    #         else:
    #             # Error during classficiation, GPT did not return a valid Classification - Priority response.
    #             return             
    #     except Exception as e:
    #         logger.error(f"Failed to classify message with OpenAI: {str(e)}")
    #         return     