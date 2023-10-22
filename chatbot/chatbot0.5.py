import os
import random
import time
import nltk
import spacy
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.tokenize import word_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import re
import psycopg2
import requests
import openai
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from time import sleep

openai.api_key = os.environ["OPENAI_API_KEY"]

class StumbleChatBot:
    def __init__(self, username, password):
        self.driver = webdriver.Chrome(ChromeDriverManager().install())
        self.username = username
        self.password = password

    def login(self):
        self.driver.get("https://www.stumblechat.com") 
        sleep(2)
        self.driver.find_element(By.ID, "login-button-id").click() 
        sleep(2)
        self.driver.find_element(By.ID, "username-input-id").send_keys(self.username)
        self.driver.find_element(By.ID, "password-input-id").send_keys(self.password)
        self.driver.find_element(By.ID, "login-submit-button-id").click()
        sleep(2)

    def fetch_messages(self):
        messages_elements = self.driver.find_elements(By.CLASS_NAME, "message-element-class")
        messages = [element.text for element in messages_elements]
        return messages

    def post_message(self, message):
        self.driver.find_element(By.ID, "post-message-input-id").send_keys(message)
        self.driver.find_element(By.ID, "post-message-button-id").click()

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
            sentiments = profile[1]
            topics = profile[2]
            data = profile[3]

        return (sentiments, topics, data)

    def save_user_profile(self, user_id, sentiments, topics, data):
        self.cur.execute("""
            INSERT INTO user_profiles (user_id, sentiments, topics, data)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id)
            DO UPDATE SET sentiments = %s, topics = %s, data = %s""",
            (user_id, sentiments, topics, data, sentiments, topics, data)
        )
        self.conn.commit()

    def save_chat_entry(self, user_id, message):
        self.cur.execute(
            "INSERT INTO chatlog (user_id, message) VALUES (%s, %s)",
            (user_id, message)
        )
        self.conn.commit()

class Chatbot:
    def __init__(self, chatlog):
        self.chatlog = chatlog

    def chat(self, user_id, message):
        sentiments, topics, data = self.chatlog.get_user_profile(user_id)
        sentiments.append(self.analyze_sentiment(message))
        topics.extend(self.analyze_topics(message))
        self.chatlog.save_user_profile(user_id, sentiments, topics, data)
        self.chatlog.save_chat_entry(user_id, message)
        response = self.generate_response(message)
        return response

    def analyze_sentiment(self, message):
        sia = SentimentIntensityAnalyzer()
        sentiment = sia.polarity_scores(message)
        return sentiment

    def analyze_topics(self, message):
        doc = self.chatlog.nlp(message)
        topics = [chunk.root.text for chunk in doc.noun_chunks]
        return topics

    def generate_response(self, message):
        prompt = f"The following is a conversation with an AI assistant. The assistant is helpful, creative, and friendly.\n\nUser: {message}\nAssistant:"
        response = openai.Completion.create(
            engine="text-davinci-002",
            prompt=prompt,
            temperature=0.8,
            max_tokens=150
        )
        return response.choices[0].text.strip()

def authenticate(username, password):
    # authenticate method implementation depends on your service
    return True

def start_cli():
    username = input("Enter your username: ")
    password = input("Enter your password: ")
    authenticated = authenticate(username, password)
    if not authenticated:
        print("Authentication failed. Exiting...")
        return
    chatlog = Chatlog(
        chatroom_url="http://your-chat-room-url",
        username="your-username",
        password="your-password",
        database_name="your-db-name",
        database_user="your-db-username",
        database_password="your-db-password"
    )
    chatbot = Chatbot(chatlog)
    stumblechat_bot = StumbleChatBot(username, password)
    stumblechat_bot.login()

    while True:
        command = input("Enter command (chat, profile, fetch, post, command, exit): ")
        if command == "chat":
            user_id = input("Enter user id: ")
            message = input("Enter your message: ")
            response = chatbot.chat(user_id, message)
            print(f"Chatbot response: {response}")
        elif command == "profile":
            user_id = input("Enter user id: ")
            sentiments, topics, data = chatlog.get_user_profile(user_id)
            print(f"Sentiments: {sentiments}")
            print(f"Topics: {topics}")
            print(f"Data: {data}")
        elif command == "fetch":
            messages = stumblechat_bot.fetch_messages()
            print("Fetched messages: ")
            for msg in messages:
                print(msg)
        elif command == "post":
            message = input("Enter the message to post: ")
            stumblechat_bot.post_message(message)
        elif command == "command":
            command = input("Enter your command: ")
            response = chatbot.generate_response(command)
            print(f"Chatbot response: {response}")
        elif command == "exit":
            print("Exiting...")
            break

if __name__ == "__main__":
    start_cli()

