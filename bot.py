import os
import uuid
import json
from typing import Callable, List, Union

from dotenv import load_dotenv
from flask import Flask, render_template, request, make_response, redirect, jsonify
from web3 import Web3
from eth_account.messages import encode_defunct

import pinecone
import openai

from langchain import LLMChain
from langchain.agents import initialize_agent, load_tools, ZeroShotAgent, AgentExecutor, Tool, LLMSingleActionAgent, AgentOutputParser
from langchain.prompts import BaseChatPromptTemplate
from langchain.memory import ConversationBufferMemory, ChatMessageHistory
from langchain.chains import ConversationChain, ConversationalRetrievalChain, RetrievalQA
from langchain.chains.conversation.memory import ConversationBufferWindowMemory
from langchain.vectorstores import Pinecone
from langchain.embeddings.openai import OpenAIEmbeddings
from llama_index import GPTSimpleVectorIndex, download_loader

from langchain.llms import OpenAI
from langchain.chat_models import ChatOpenAI
from langchain import SerpAPIWrapper, LLMChain
from typing import List, Union
from langchain.schema import AgentAction, AgentFinish, HumanMessage
from pathlib import Path
from llama_index import download_loader

import re



load_dotenv()
history = ChatMessageHistory()

env_vars = [
    'OPENAI_API_KEY',
    'SERPAPI_API_KEY',
    'ALCHEMY_API_KEY',
    'PINECONE_API_KEY',
    'PINECONE_ENVIRONMENT',
]

os.environ.update({key: os.getenv(key) for key in env_vars})
os.environ['WEB3_PROVIDER'] = f"https://polygon-mumbai.g.alchemy.com/v2/{os.environ['ALCHEMY_API_KEY']}"
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT")
ORGANIZATION = os.getenv("ORGANIZATION")

# Initialize web3
web3 = Web3(Web3.HTTPProvider(os.environ['WEB3_PROVIDER']))

#Initialize LLM
llm=ChatOpenAI(
    openai_api_key=os.environ['OPENAI_API_KEY'],
    temperature=0.1,
    #model_name='gpt-3.5-turbo'
    model_name='gpt-4'
)


# Prepare augmented query

pinecone.init(api_key=os.environ['PINECONE_API_KEY'], enviroment=os.environ['PINECONE_ENVIRONMENT'])
pinecone.whoami()
#index_name = 'hc'
index_name = 'hctest'
index = pinecone.Index(index_name)

embed_model = "text-embedding-ada-002"

primer = """

You are Amy, a friendly and helpful virtual customer support agent for Ledger, a French crypto company headed by CEO Pascal Gauthier.

You might receive questions about Ledger products such as the Ledger Nano S (no battery, low storage), Nano X (bluetooth, large storage, battery), Nano S Plus (large storage, no bluetooth, no battery), and Ledger Live, but not Ledger Blue. 

The official Ledger store is located at https://shop.ledger.com/. For authorized resellers, please visit https://www.ledger.com/reseller/ , do not modify or share any other links for these purposes. 

When asked about Ledger Stax, tell users it is not released yet but can be preordered at https://shop.ledger.com/.

When users inquire about supported crypto assets, coins and tokens supported by Ledger Live, it is crucial to strictly use the provided Crypto Asset List link to verify support. 

The link to the Crypto Asset List is: https://support.ledger.com/hc/en-us/articles/10479755500573?docs=true/. Refrain from using any other links.

Here's a guide on using the Crypto Asset List:

- The list is organized into bullet points with the following format: | network | token symbol | contract address | token name | countervalue
- If a coin or token is on the list, it is supported in Ledger Live.
- The list is not case-sensitive, so "BTC" and "btc" are treated as identical.
- If a coin or token has "countervalues disabled" as its countervalue, it is supported in Ledger Live, but its value will not be displayed.
- When a coin or token is supported, include information about the supported network.
- ALWAYS provide the following link to the Crypto Asset List for users to find more information: https://support.ledger.com/?docs=true/ . Do not share any other links for this purpose.


NFTs are supported on Ethereum and Polygon.

If a question is unclear or lacks detail, ask for more information instead of assuming. If uncertain about an answer, be honest and request clarification. Do not advise users to reset devices or firmware unless absolutely necessary.

If users want to speak with a human agent, direct them to open a ticket or live chat at https://support.ledger.com/?docs=true/ . Remind users not to share their 24-word recovery phrase with anyone, including Ledger employees, and not to enter it into any apps like Ledger Live. Ledger Support can be reached through email, live chat at https://support.ledger.com/ and daily YouTube live support sessions at https://www.youtube.com/@Ledger/streams/.

VERY IMPORTANT:

- When providing answers, always mention the source of your information, whether it is from an official Help Center article, tutorial, or another resource. If possible, include a direct link to the relevant resource in your response.
- Always provide the correct URL link to relevant Help Center articles or tutorials when responding to inquiries. Help Center links should always have the following format: "https://support.ledger.com/hc/en-us/articles/XXXXXXXXXXX" where the Xs represent the specific article ID. Don't share a link if uncertain of its accuracy.
- Direct users who want to learn more about Ledger products or compare devices to https://www.ledger.com/.
- If a user reports being scammed, provide this link ONLY: " https://support.ledger.com/?docs=true/ " for them to contact a live agent.

Begin by briefly greeting the user. Remember, your primary goal is to keep the user's crypto assets safe and protect them against scams.

"""


# Load the VALID_ARTICLE_IDS dictionary from a .txt file
with open("/home/dan/langchain_projects/hcBot/documents/valid_urls.txt", "r") as infile:
    VALID_ARTICLE_IDS = json.load(infile)

def correct_url(url):
    if not url.startswith("https://support.ledger.com/hc/en-us/articles/"):
        return url

    article_id = re.search(r"https://support\.ledger\.com/hc/en-us/articles/(\d+)", url)
    if article_id and article_id.group(1) in VALID_ARTICLE_IDS:
        corrected_url = f"https://support.ledger.com/hc/en-us/articles/{article_id.group(1)}-{VALID_ARTICLE_IDS[article_id.group(1)]}"
        return corrected_url
    else:
        # If the article ID is not valid or doesn't match an existing article, replace it with a default URL or an error message.
        return "https://support.ledger.com/?docs=true/"

# #####################################################


# Define Flask app
app = Flask(__name__, static_folder='static')

# Define authentication function
def authenticate(signature):
    w3 = Web3(Web3.HTTPProvider(os.environ['WEB3_PROVIDER']))
    message = "Access to chat bot"
    message_hash = encode_defunct(text=message)
    signed_message = w3.eth.account.recover_message(message_hash, signature=signature)
    balance = int(contract.functions.balanceOf(signed_message).call())
    if balance > 0:
        token = uuid.uuid4().hex
        response = make_response(redirect('/gpt'))
        response.set_cookie("authToken", token, httponly=True, secure=True, samesite="strict")
        return response
    else:
        return "You don't have the required NFT!"

# Define function to check for authToken cookie
def has_auth_token(request):
    authToken = request.cookies.get("authToken")
    return authToken is not None

# Define Flask endpoints
@app.route("/")
def home():
    return render_template("auth.html")

@app.route("/auth")
def auth():
    signature = request.args.get("signature")
    response = authenticate(signature)
    return response

@app.route("/gpt")
def gpt():
    if has_auth_token(request):
        return render_template("index.html")
    else:
        return redirect("/")

@app.route('/api', methods=['POST'])
def react_description():
    user_input = request.json.get('user_input')
    query = user_input
    try:

        res_embed = openai.Embedding.create(
            input=[user_input],
            engine=embed_model
        )

        xq = res_embed['data'][0]['embedding']

        res_query = index.query(xq, top_k=5, include_metadata=True)

        contexts = [item['metadata']['text'] for item in res_query['matches']]

        augmented_query = "\n\n---\n\n".join(contexts)+"\n\n-----\n\n"+user_input

        res = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": primer},
                {"role": "user", "content": augmented_query}
            ]
        )
        response = res['choices'][0]['message']['content']
        print(response)
        return jsonify({'output': response})
    except ValueError as e:
        print(e)
        return jsonify({'output': 'Sorry, could you please repeat the question?'})


ADDRESS = "0xb022C9c672592c274397557556955eE968052969"
ABI = [{"inputs":[{"internalType":"string","name":"_name","type":"string"},{"internalType":"string","name":"_symbol","type":"string"}],"stateMutability":"nonpayable","type":"constructor"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"owner","type":"address"},{"indexed":True,"internalType":"address","name":"approved","type":"address"},{"indexed":True,"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"Approval","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"owner","type":"address"},{"indexed":True,"internalType":"address","name":"operator","type":"address"},{"indexed":False,"internalType":"bool","name":"approved","type":"bool"}],"name":"ApprovalForAll","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"previousOwner","type":"address"},{"indexed":True,"internalType":"address","name":"newOwner","type":"address"}],"name":"OwnershipTransferred","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"from","type":"address"},{"indexed":True,"internalType":"address","name":"to","type":"address"},{"indexed":True,"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"Transfer","type":"event"},{"inputs":[{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"approve","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"getApproved","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"operator","type":"address"}],"name":"isApprovedForAll","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"owner","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"ownerOf","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"renounceOwnership","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"to","type":"address"},{"internalType":"string","name":"tokenURI","type":"string"}],"name":"safeMint","outputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"safeTransferFrom","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"tokenId","type":"uint256"},{"internalType":"bytes","name":"_data","type":"bytes"}],"name":"safeTransferFrom","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"operator","type":"address"},{"internalType":"bool","name":"approved","type":"bool"}],"name":"setApprovalForAll","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"bytes4","name":"interfaceId","type":"bytes4"}],"name":"supportsInterface","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"symbol","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"index","type":"uint256"}],"name":"tokenByIndex","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"uint256","name":"index","type":"uint256"}],"name":"tokenOfOwnerByIndex","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"tokenURI","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"transferFrom","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"newOwner","type":"address"}],"name":"transferOwnership","outputs":[],"stateMutability":"nonpayable","type":"function"}]
contract = web3.eth.contract(address=ADDRESS, abi=ABI)

# Start the Flask app
if __name__ == '__main__':
    app.run(port=8000, debug=True)
