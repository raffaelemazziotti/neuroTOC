import pandas as pd
import xml.etree.ElementTree as ET
import gensim
from gensim import corpora
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer
import pyLDAvis.gensim_models as gensimvis
import pyLDAvis
import matplotlib.pyplot as plt
import nltk
import string

# Download required NLTK data
nltk.download('punkt_tab')
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('wordnet')


# Load and parse XML data
def parse_xml(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    data = []

    for journal in root.findall('Journal'):
        for article in journal.findall('Article'):
            title = article.find('Title').text or ""
            abstract = article.find('Abstract').text or ""
            data.append(title + " " + abstract)

    return data


# Text Preprocessing
def preprocess_text(texts):
    stop_words = set(stopwords.words('english'))
    lemmatizer = WordNetLemmatizer()

    processed_texts = []
    for text in texts:
        tokens = word_tokenize(text.lower())
        tokens = [t for t in tokens if t.isalpha()]  # Remove punctuation/numbers
        tokens = [t for t in tokens if t not in stop_words]  # Remove stopwords
        tokens = [lemmatizer.lemmatize(t) for t in tokens]  # Lemmatize words
        processed_texts.append(tokens)
    return processed_texts


# Perform LDA Topic Modeling
def perform_lda(processed_texts, num_topics=5):
    dictionary = corpora.Dictionary(processed_texts)
    corpus = [dictionary.doc2bow(text) for text in processed_texts]

    lda_model = gensim.models.LdaModel(corpus,
                                       num_topics=num_topics,
                                       id2word=dictionary,
                                       passes=10,
                                       random_state=42)

    # Display the topics
    for idx, topic in lda_model.print_topics(-1):
        print(f"Topic {idx}: {topic}\n")

    return lda_model, corpus, dictionary


# Visualize LDA Topics
def visualize_lda(lda_model, corpus, dictionary, output_file="lda_visualization.html"):
    vis = gensimvis.prepare(lda_model, corpus, dictionary)
    pyLDAvis.save_html(vis, output_file)
    print(f"LDA Visualization saved to {output_file}")


# Main Execution
texts = parse_xml("all_journals_toc.xml")
processed_texts = preprocess_text(texts)
lda_model, corpus, dictionary = perform_lda(processed_texts, num_topics=5)
visualize_lda(lda_model, corpus, dictionary)
