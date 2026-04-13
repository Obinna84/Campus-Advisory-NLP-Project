import pandas as pd
from sklearn.model_selection import train_test_split
import spacy
from spacy.training import Example
from spacy.util import minibatch, compounding
import random

df = pd.read_csv('data/sample_alerts.csv', encoding='latin-1')
print(df.head())

df['alert'] = df['description'].fillna('') + " Location: " + df['location'].fillna('')

labels = df['category'].unique()
print(labels)

train_data = []
for _, row in df.iterrows():
    text = row['alert'].strip()
    if not text or text == " Location: ":
        continue  # Skip empty rows
    categories = {label: 1.0 if label == row['category'] else 0.0 for label in labels}
    train_data.append((text, {"cats": categories}))

train, val = train_test_split(train_data, test_size=0.2, random_state=42)

print(f"Training data size: {len(train)}")
print(f"Validation data size: {len(val)}")

nlp = spacy.load("en_core_web_sm")
textcat = nlp.add_pipe("textcat", last=True)
for label in labels:
    textcat.add_label(label)

train_examples = []
for text, annotations in train:
    doc = nlp.make_doc(text)
    example = Example.from_dict(doc, annotations)
    train_examples.append(example)

nlp.initialize(lambda: train_examples)
optimizer = nlp.create_optimizer()

for epoch in range(10):
    random.shuffle(train_examples)
    losses = {}
    batches = minibatch(train_examples, size=compounding(4.0, 32.0, 1.001))
    for batch in batches:
        nlp.update(batch, sgd=optimizer, losses=losses)
    print(f"Epoch {epoch+1}, Losses: {losses}")

val_examples = []
for text, annotations in val:
    doc = nlp.make_doc(text)
    example = Example.from_dict(doc, annotations)
    val_examples.append(example)


def evaluate_model(nlp, val_examples):
    correct = 0
    total = len(val_examples)
    for example in val_examples:
        doc = nlp(example.text)
        predicted_label = max(doc.cats, key=doc.cats.get)
        true_label = max(example.reference.cats, key=example.reference.cats.get)
        if predicted_label == true_label:
            correct += 1
    accuracy = correct / total
    scores = nlp.evaluate(val_examples)
    print(f"Validation Accuracy: {accuracy:.2f}")
    print(f"NER F1 Score: {scores['ents_f']}")

evaluate_model(nlp, val_examples)

def predict_category(nlp, text):
    doc = nlp(text)
    predicted_label = max(doc.cats, key=doc.cats.get)
    return predicted_label


# Test Cases for Model Predictions
test_text = ["Suspicious activity reported near the library.",
             "Fire alarm triggered in the dormitory.",
             "Robbery reported near U St, Weapons were involved.",
             "Fight reported near Drew Hall, two students involved with both receiving minor injuries.",
             "Police Department is investigating a report of a sexual assault near Blackburn.",
             "Police Department is investigating shooting near Florida Ave, two victims were rushed to the hospital with non-life-threatening injuries.",
             "Police Department is investigating a report of an attempted robbery near 14th St and U St, this is not a Howard related incident.",
             "Police Department is investigating a report of a stabbing near 7th St and V St, this is not a Howard related incident.",
             "Police Department is investigating a report of a car jacking near Axis, this is a Howard related incident.",
             "Shots fired reported near Georgia Ave and Euclid St, this is a Howard related incident."
             ]
for text in test_text:
    predicted_category = predict_category(nlp, text)
    print(f"Predicted category for '{text}': {predicted_category}")

#nlp.to_disk("spacy_model")
