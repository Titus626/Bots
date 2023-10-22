import os
import nltk
import spacy
import time
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.tokenize import word_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import re
import psycopg2
import requests
import openai
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import asyncio
import websockets
                
openai.api_key = os.environ["OPENAI_API_KEY"]

class Chatlog:
    def __init__(self, chatroom_url, username, password, database_name, database_user, database_password):
        self.chatroom_url = chatroom_url
        self.username = username
        self.password = password
        self.database_name = database_name
        self.database_user = database_user
        self.database_password = database_password
        self.nlp = spacy.load("en_core_web_sm")  

        self.conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database=database_name,
            user=database_user,
            password=database_password
        )
        self.cur = self.conn.cursor()
        self.upgrade_database()

    def upgrade_database(self):
        self.cur.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'user_profiles')"
        )
        user_profiles_table_exists = self.cur.fetchone()[0]

        self.cur.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'chatlog')"
        )
        chatlog_table_exists = self.cur.fetchone()[0]

        if not user_profiles_table_exists:
            self.cur.execute("""
                CREATE TABLE user_profiles (
                    user_id SERIAL PRIMARY KEY,
                    sentiments TEXT,
                    topics TEXT,
                    data JSONB
                )
            """)
            self.conn.commit()

        if not chatlog_table_exists:
            self.cur.execute("""
                CREATE TABLE chatlog (
                    entry_id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    message TEXT,
                    timestamp TIMESTAMP DEFAULT NOW()
                )
            """)
            self.conn.commit()

    def get_user_profile(self, user_id):
        sentiments = []
        topics = []
        data = {}

        self.cur.execute(
            "SELECT * FROM user_profiles WHERE user_id = %s",
            (user_id,)
        )
        profile = self.cur.fetchone()

        if profile:
            sentiments = [int(sentiment) for sentiment in profile[1].split(",")]
            topics = profile[2].split(",")
            data = profile[3]

        return {
            "user_id": user_id,
            "avg_sentiment": sum(sentiments) / len(sentiments),
            "most_common_topic": max(topics, key=topics.count),
            "data": data
        }

    def create_user_profile(self, user_id, sentiments, topics, data):
        sentiments_str = ",".join(str(sentiment) for sentiment in sentiments)
        topics_str = ",".join(topics)

        self.cur.execute(
            "INSERT INTO user_profiles (user_id, sentiments, topics, data) VALUES (%s, %s, %s, %s)",
            (user_id, sentiments_str, topics_str, data)
        )
        self.conn.commit()

    def update_user_profile(self, user_id, sentiments, topics, data):
        sentiments_str = ",".join(str(sentiment) for sentiment in sentiments)
        topics_str = ",".join(topics)

        self.cur.execute(
            "UPDATE user_profiles SET sentiments = %s, topics = %s, data = %s WHERE user_id = %s",
            (sentiments_str, topics_str, data, user_id)
        )
        self.conn.commit()

    def get_chat_history(self, user_id, limit=10):
        self.cur.execute(
            "SELECT * FROM chatlog WHERE user_id = %s ORDER BY timestamp DESC LIMIT %s",
            (user_id, limit)
        )
        return self.cur.fetchall()

    def add_chat_entry(self, user_id, message):
        self.cur.execute(
            "INSERT INTO chatlog (user_id, message) VALUES (%s, %s)",
            (user_id, message)
        )
        self.conn.commit()
    def login_to_chat(self):
        self.driver.get(self.chatroom_url)
        time.sleep(2)  # Wait for page to load

        username_input = self.driver.find_element_by_name('username')
        password_input = self.driver.find_element_by_name('password')

        username_input.send_keys(self.username)
        password_input.send_keys(self.password)

        submit_button = self.driver.find_element_by_css_selector("button[type='submit']")
        submit_button.click()
        time.sleep(2)  # Wait for login to process

    def get_chat_messages(self):
        chat_messages = self.driver.find_elements_by_css_selector(".chat-message")

        messages = []
        for message in chat_messages:
            user_id = message.get_attribute("data-user-id")
            text = message.text
            messages.append({
                "user_id": user_id,
                "message": text,
            })

        return messages

    def run(self):
        self.login_to_chat()

        while True:
            messages = self.get_chat_messages()
            for message in messages:
                user_id = message['user_id']
                text = message['message']
                self.store_chatlog(user_id, text)
            time.sleep(5)  # Wait for new messages
from openai import GPT3Completion

class Chatbot:
    def __init__(self, chatlog):
        self.chatlog = chatlog
        self.gpt3 = GPT3Completion(api_key="your_openai_api_key")  # replace with your actual key

    def generate_response(self, message_dict):
        user_id = message_dict["user"]
        message = message_dict["message"]

        self.chatlog.store_chatlog(user_id, message)

        doc = self.chatlog.nlp(message)
        sentiments = [sentence._.sentiment.polarity for sentence in doc.sents]
        topics = [token.lemma_ for token in doc if token.pos_ in ["NOUN", "PROPN"]]

        user_profile = self.chatlog.get_user_profile(user_id)
        existing_sentiments = user_profile.get("avg_sentiment", [])
        existing_topics = user_profile.get("most_common_topic", [])
        existing_data = user_profile.get("data", {})

        updated_sentiments = existing_sentiments + sentiments
        updated_topics = existing_topics + topics

        if user_profile:
            self.chatlog.update_user_profile(user_id, updated_sentiments, updated_topics, existing_data)
        else:
            self.chatlog.create_user_profile(user_id, updated_sentiments, updated_topics, existing_data)

        # generate a context-aware response using the GPT-3 model
        context = {
            "sentiment": sum(updated_sentiments) / len(updated_sentiments) if updated_sentiments else 0,
            "topics": updated_topics,
            "message": message,
        }
        response = self.gpt3.generate_message(context)
        return response
    
class GPT3Completion:
    def __init__(self, api_key):
        self.api_key = api_key

    def generate_message(self, context):
        prompt = f"The user's sentiment is {context['sentiment']}. They are talking about {', '.join(context['topics'])}. Their message is: {context['message']}. How should we respond?"

        response = openai.Completion.create(
            engine="text-davinci-002",
            prompt=prompt,
            temperature=0.7,
            max_tokens=100
        )
        return response.choices[0].text.strip()


class Chatbot:
    def __init__(self, chatlog):
        self.chatlog = chatlog
        self.gpt3 = GPT3Completion(api_key="your_openai_api_key")  # replace with your actual key

    def generate_response(self, message_dict):
        user_id = message_dict["user"]
        message = message_dict["message"]

        self.chatlog.store_chatlog(user_id, message)

        doc = self.chatlog.nlp(message)
        sentiments = [sentence._.sentiment.polarity for sentence in doc.sents]
        topics = [token.lemma_ for token in doc if token.pos_ in ["NOUN", "PROPN"]]

        user_profile = self.chatlog.get_user_profile(user_id)
        existing_sentiments = user_profile.get("avg_sentiment", [])
        existing_topics = user_profile.get("most_common_topic", [])
        existing_data = user_profile.get("data", {})

        updated_sentiments = existing_sentiments + sentiments
        updated_topics = existing_topics + topics

        if user_profile:
            self.chatlog.update_user_profile(user_id, updated_sentiments, updated_topics, existing_data)
        else:
            self.chatlog.create_user_profile(user_id, updated_sentiments, updated_topics, existing_data)

        # generate a context-aware response using the GPT-3 model
        context = {
            "sentiment": sum(updated_sentiments) / len(updated_sentiments) if updated_sentiments else 0,
            "topics": updated_topics,
            "message": message,
        }
        response = self.gpt3.generate_message(context)
        return response

    def process_command(self, command):
        response = openai.Completion.create(
            engine="davinci",
            prompt=command,
            temperature=0.7,
            max_tokens=100
        )
        return response.choices[0].text.strip()
    
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class ChatInterface:
    def __init__(self, chatbot):
        self.chatbot = chatbot
        # Start the WebDriver and load the page
        self.wd = webdriver.Chrome()
        self.wait = WebDriverWait(self.wd, 10)

    def start(self, url):
        self.wd.get(url)

    def login(self, username, password):
        username_input = self.wait.until(EC.presence_of_element_located((By.ID, 'username_input')))  # replace 'username_input' with the actual ID
        password_input = self.wait.until(EC.presence_of_element_located((By.ID, 'password_input')))  # replace 'password_input' with the actual ID
        username_input.send_keys(username)
        password_input.send_keys(password)
        password_input.send_keys(Keys.RETURN)

    def send_message(self, message):
        message_input = self.wait.until(EC.presence_of_element_located((By.ID, 'message_input')))  # replace 'message_input' with the actual ID
        message_input.send_keys(message)
        message_input.send_keys(Keys.RETURN)

    def read_message(self):
        message_output = self.wait.until(EC.presence_of_element_located((By.ID, 'message_output')))  # replace 'message_output' with the actual ID
        return message_output.text

    def run(self, username, password, url):
        self.start(url)
        self.login(username, password)
        while True:
            time.sleep(1)
            new_message = self.read_message()
            if new_message:
                response = self.chatbot.generate_response({"user": username, "message": new_message})
                self.send_message(response)
if __name__ == "__main__":
    chatlog = Chatlog(
        chatroom_url="http://your-chat-room-url",
        username="your-username",
        password="your-password",
        database_name="your-db-name",
        database_user="your-db-username",
        database_password="your-db-password"
    )
    chatbot = Chatbot(chatlog)
    chat_interface = ChatInterface(chatbot)
    chat_interface.run("your-username", "your-password", "http://your-chat-room-url")
