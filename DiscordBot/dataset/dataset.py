import pandas as pd
import re
import yaml
from yaml.loader import SafeLoader
import json
import numpy as np

# scams generated from chatgpt and some links replaced with known scams from https://cryptoscamdb.org/scams
scams = "DiscordBot/dataset/generated_scams.tsv" 

# https://www.kaggle.com/datasets/aagghh/crypto-telegram-groups/data
# group messages from Telegram Crypto group chats, assumed to be non scam
bittrex = "DiscordBot/dataset/group_messages_bittrex.json"  
kucoin = "DiscordBot/dataset/group_messages_kucoin.json"

# Known Scam Links: https://cryptoscamdb.org/scams
links = "DiscordBot/dataset/urls.yaml"

def parse_scam_links(file):
    with open(file, 'r') as f:
        yaml_data = list(yaml.load_all(f, Loader=SafeLoader))

    scam_links = {
        "data": "scam links",
        "source": "CryptoScamDb",
        "links": [],
    }
    for i in range(len(yaml_data[0])):
        data = yaml_data[0][i]
        scam_links["links"].append({ "url": data["url"], "type": data["category"]})
    
    with open("DiscordBot/dataset/scam_links.json", "w") as outfile: 
        json.dump(scam_links, outfile)
    
    return scam_links


def generate_dataset(files, size):
    scam_file = files[0]
    scams = pd.read_csv(scam_file, sep="\t", dtype=str)
    non_scams_file_1 = open(files[1])
    non_scams_1 = json.load(non_scams_file_1)
    non_scams_file_1.close()

    non_scams_file_2 = open(files[2])
    non_scams_2 = json.load(non_scams_file_2)
    non_scams_file_2.close()

    dataset = {
        "name": "crypto dataset",
        "messages": []
    }

    for i in range(len(scams)):
        dataset["messages"].append({ "content": scams.loc[i, "Message"], "label": scams.loc[i, "Label"] })
    
    non_size = size - len(scams)
    non_size_1 = int(np.ceil(non_size / 2))  # for dataset 1
    non_size_2 = int(np.floor(non_size / 2))  # for dataset 2

    for i in range(100, 100 + non_size_1):
        dataset["messages"].append( { "content": non_scams_1[i]['message'], "label": "non_scam"} )
        print(non_scams_1[i]['message'])

    for i in range(100, 100 + non_size_2):
        dataset["messages"].append( { "content": non_scams_2[i]['message'], "label": "non_scam"} )
        print(non_scams_2[i]['message'])
    
    with open("DiscordBot/dataset/dataset.json", "w") as outfile: 
        json.dump(dataset, outfile)
    
    return dataset


print(generate_dataset([scams, kucoin, bittrex], 110))
# parse_scam_links(links)