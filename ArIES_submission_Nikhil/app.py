import streamlit as st
from PyPDF2 import PdfReader
from langchain.text_splitter import CharacterTextSplitter
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
from transformers import T5Tokenizer, T5ForConditionalGeneration, AutoTokenizer
from Templates import css, bot_template, user_template, render_pdf
# from dotenv import load_dotenv

# Define a class for FAISS retriever
class FAISSRetriever:
    def __init__(self, index, texts, embeddings):
        self.index = index
        self.texts = texts
        self.embeddings = embeddings

    def get_relevant_documents(self, query, k=5):
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        query_embedding = model.encode([query])
        D, I = self.index.search(np.array(query_embedding), k=k)
        return [self.texts[i] for i in I[0]]

# Function to extract text from PDF files
def get_pdf_text(pdf_docs):
    text = ""
    for pdf in pdf_docs:
        pdf_reader = PdfReader(pdf)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text

# Function to split text into manageable chunks
def get_text_chunks(text):
    text_splitter = CharacterTextSplitter(
        separator='\n',
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    chunks = text_splitter.split_text(text)
    return chunks

# Function to create FAISS vector store from text chunks
def get_vectorstore(text_chunks):
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    embeddings = model.encode(text_chunks, convert_to_tensor=False)
    embeddings = np.array(embeddings)
    
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)
    
    return FAISSRetriever(index=index, texts=text_chunks, embeddings=embeddings)

# Function to initialize the T5 conversational model
def get_conversation_model():
    local_model_path = "MBZUAI/LaMini-T5-738M"
    tokenizer = T5Tokenizer.from_pretrained(local_model_path)
    model = T5ForConditionalGeneration.from_pretrained(local_model_path)
    return tokenizer, model

# Function to generate response from T5 model given an input query
def generate_response(input_text, tokenizer, model, max_length=100):
    input_ids = tokenizer.encode(input_text, return_tensors="pt")
    response = model.generate(input_ids, max_length=max_length, pad_token_id=tokenizer.pad_token_id)
    return tokenizer.decode(response[0], skip_special_tokens=True)

# Main function to run the Streamlit app
def main():
    # Load environment variables from .env file
    # load_dotenv()
    st.set_page_config(page_title="Chat with multiple PDFs", page_icon=":books:")
    st.write(css, unsafe_allow_html=True)
    
    if "conversation" not in st.session_state:
        st.session_state.conversation = None

    if "file_details" not in st.session_state:
        st.session_state.file_details = []

    st.header("Chat with multiple PDFs :books:")
    query = st.text_input("Ask a question about your documents:")

    if query and "conversation" in st.session_state:
        # Retrieve FAISS retriever from session state
        vectorstore = st.session_state.conversation
        relevant_documents = vectorstore.get_relevant_documents(query)
        
        if relevant_documents:
            # Join relevant documents into one large text
            combined_text = "\n".join(relevant_documents)
            # Generate response using T5 model
            tokenizer, model = get_conversation_model()
            response = generate_response(combined_text, tokenizer, model)
            st.write(user_template.replace("{{MSG}}", query), unsafe_allow_html=True)
            st.write(bot_template.replace("{{MSG}}", response), unsafe_allow_html=True)

    with st.sidebar:
        st.subheader("Your documents")
        pdf_docs = st.file_uploader(
            "Upload your PDFs here and click on 'Process'", accept_multiple_files=True)
        if st.button("Process"):
            if pdf_docs:
                with st.spinner("Processing..."):
                    raw_text = get_pdf_text(pdf_docs)
                    text_chunks = get_text_chunks(raw_text)
                    vectorstore = get_vectorstore(text_chunks)
                    st.session_state.conversation = vectorstore
                    st.session_state.file_details = [{"name": pdf.name, "size": pdf.size, "data": pdf} for pdf in pdf_docs]
                    st.success("Processing completed. Now ask a question!")
                    
            if st.session_state.file_details:
                st.markdown("<div class='file-review'><h3>File Preview</h3>", unsafe_allow_html=True)
                for file_detail in st.session_state.file_details:
                    st.markdown(f"<p><strong>Name:</strong> {file_detail['name']}<br><strong>Size:</strong> {file_detail['size']} bytes</p>", unsafe_allow_html=True)
                    # Render PDF file in iframe
                    pdf_data = file_detail['data'].getvalue()
                    pdf_display = render_pdf(pdf_data)
                    st.markdown(pdf_display, unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

if __name__ == '__main__':
    main()
