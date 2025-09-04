import streamlit as st
import openai
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import os
from dotenv import load_dotenv
load_dotenv()  # Reads .env file
openai_api_key = os.environ.get("OPENAI_API_KEY")  # Optional, just to check

# Sample FAQ data on agents and their benefits
faq_data = [
    # Orders
    {"question": "How can I track my order?", "answer": "After placing an order, you'll receive a tracking link via email."},
    {"question": "Can I cancel my order after placing it?", "answer": "Yes, you can cancel before the order is shipped. Once shipped, cancellation is not possible."},
    {"question": "How do I modify my order?", "answer": "Please contact our support team before your order is shipped to make changes."},
    {"question": "Why is my order delayed?", "answer": "Delays can happen due to stock issues, courier delays, or high demand periods. Check your tracking link for updates."},

    # Shipping & Delivery
    {"question": "Do you offer international shipping?", "answer": "Yes, we ship to most countries worldwide."},
    {"question": "How much is the shipping fee?", "answer": "Shipping costs vary depending on your location and the weight of your order."},
    {"question": "How long does delivery take?", "answer": "Domestic orders usually take 3–7 business days, and international orders 7–15 business days."},
    {"question": "Can I change my delivery address after ordering?", "answer": "Yes, contact support before your order is dispatched to update the address."},
    {"question": "What happens if I miss the delivery?", "answer": "The courier will attempt re-delivery or leave instructions to pick up from a nearby location."},
    {"question": "What shipping methods do you offer?", "answer": "We currently offer multiple shipping methods:\n- Standard Shipping (3–7 business days)\n- Express Shipping (1–3 business days)\n- Same-Day / Next-Day Delivery (in select cities)\n- International Shipping (7–15 business days)\n- Free Shipping (on orders above a certain amount)"},

    # Returns & Refunds
    {"question": "What is your return policy?", "answer": "You can return items within 30 days of purchase."},
    {"question": "How do I request a refund?", "answer": "Login to your account, go to 'My Orders', select the item, and click 'Request Refund'."},
    {"question": "How long does it take to process a refund?", "answer": "Refunds are usually processed within 5–10 business days after we receive the returned product."},
    {"question": "Can I return a sale item?", "answer": "Yes, unless marked as 'Final Sale', discounted items are eligible for returns."},
    {"question": "Who pays for return shipping?", "answer": "Return shipping costs are covered by us if the item is defective or incorrect. Otherwise, the customer pays."},

    # Products
    {"question": "Are your products genuine?", "answer": "Yes, we only sell 100% authentic and verified products."},
    {"question": "How can I check product availability?", "answer": "On each product page, you can see stock availability before adding to cart."},
    {"question": "Do you offer warranties on products?", "answer": "Yes, many products come with a manufacturer’s warranty. Check product details for warranty info."},
    {"question": "How can I find my size?", "answer": "Refer to the size chart available on each product page."},
    {"question": "Can I preorder upcoming products?", "answer": "Yes, preorder is available for select items. They will be shipped as soon as stock arrives."},

    # Payments
    {"question": "What payment methods do you accept?", "answer": "We accept credit cards, debit cards, PayPal, and other local payment options."},
    {"question": "Is my payment information secure?", "answer": "Yes, all transactions are encrypted and processed through secure payment gateways."},
    {"question": "Can I pay cash on delivery?", "answer": "Yes, cash on delivery is available in select regions."},
    {"question": "Why was my payment declined?", "answer": "This may be due to insufficient funds, incorrect details, or bank restrictions. Please try another method."},

    # Accounts
    {"question": "How to reset my password?", "answer": "Go to settings → account → reset password."},
    {"question": "How do I create an account?", "answer": "Click 'Sign Up' on our homepage and follow the instructions."},
    {"question": "Can I checkout without creating an account?", "answer": "Yes, we offer a guest checkout option."},
    {"question": "How do I update my account details?", "answer": "Login, go to 'My Account', and update your personal or payment information."},

    # Support
    {"question": "What are your support hours?", "answer": "Our support team is available from 9 AM to 6 PM, Monday to Friday."},
    {"question": "How can I contact customer support?", "answer": "You can reach us via live chat, email, or phone from the contact page."},
    {"question": "Do you offer live chat support?", "answer": "Yes, live chat is available during business hours."},

    # Loyalty & Discounts
    {"question": "Do you have a loyalty program?", "answer": "Yes, you earn points for every purchase, which can be redeemed for discounts."},
    {"question": "How can I use a discount code?", "answer": "Enter the code at checkout in the 'Promo Code' field."},
    {"question": "Can I use multiple discount codes?", "answer": "No, only one discount code can be applied per order."},

    # Miscellaneous
    {"question": "Do you have a mobile app?", "answer": "Yes, our mobile app is available on iOS and Android."},
    {"question": "Can I buy gift cards?", "answer": "Yes, digital and physical gift cards are available on our website."},
    {"question": "Are there seasonal sales?", "answer": "Yes, we offer seasonal discounts during events like Black Friday, Cyber Monday, and New Year."}
]

# Initialize the GPT-4o mini model
chat_model = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

# Create a template for chatbot responses
faq_template = PromptTemplate(
    input_variables=["question", "faq_data"],
    template="You are an AI chatbot. Answer this question based on the provided FAQ data:\n{faq_data}\nQuestion: {question}"
)

# Create a chain for handling chatbot interactions
faq_chain = LLMChain(
    prompt=faq_template,
    llm=chat_model
)

# Streamlit app
st.title("🛒 E-Commerce Customer Support")
st.subheader("Ask me anything about orders, shipping, returns, payments, and more!")


# Initialize session state to store conversation
if "history" not in st.session_state:
    st.session_state.history = []

# Callback function to clear input
def clear_input():
    st.session_state.user_input = ""
    
# User input
# Initialize session state for the input if not already set
if 'input_value' not in st.session_state:
    st.session_state.input_value = ""

# Create a form
with st.form(key="my_form"):
    # Text input bound to session state
    user_input = st.text_input("", value="", key="user_input")
    submit_button = st.form_submit_button("Submit")

# Handle form submission
if submit_button:
    
    # Get chatbot response
    response = faq_chain.run({"question": user_input, "faq_data": faq_data})
    # Store conversation in session state
    st.session_state.history.append({"user": user_input, "bot": response})
    st.session_state.input_value = ""

# Display conversation history in descending order (latest first)
for chat in reversed(st.session_state.history):
    st.markdown(f"**You:** {chat['user']}")
    st.markdown(f"**Support:** {chat['bot']}")
    
    



# Note: Streamlit will automatically update the text input to reflect the cleared session state

