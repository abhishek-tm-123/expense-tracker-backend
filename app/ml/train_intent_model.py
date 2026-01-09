import pandas as pd
import joblib
import re
import nltk
from nltk.stem import WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from sklearn.calibration import CalibratedClassifierCV
from pathlib import Path

# Ensure NLTK data is available
try:
    nltk.download('wordnet', quiet=True)
    nltk.download('omw-1.4', quiet=True)
except Exception:
    pass

lemmatizer = WordNetLemmatizer()

def preprocess_text(text):
    # Lowercase, remove special chars, and lemmatize
    text = text.lower()
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    tokens = text.split()
    lemmatized = [lemmatizer.lemmatize(w) for w in tokens]
    return " ".join(lemmatized)

BASE_DIR = Path(__file__).resolve().parent

# Load data
df = pd.read_csv(BASE_DIR / "intent_dataset.csv")

# Preprocess all text
df['processed_text'] = df['text'].apply(preprocess_text)

X = df["processed_text"]
y = df["intent"]

# Pipeline
# Note: We use the base model inside CalibratedClassifierCV
base_clf = LogisticRegression(
    max_iter=1000,
    class_weight="balanced"
)

calibrated_clf = CalibratedClassifierCV(base_clf, cv=5, method='sigmoid')

pipeline = Pipeline([
    (
        "vectorizer",
        TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.9
        )
    ),
    (
        "clf",
        calibrated_clf
    )
])

# Train-test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.15, random_state=42, stratify=y
)

pipeline.fit(X_train, y_train)

# Evaluate
y_pred = pipeline.predict(X_test)
print(classification_report(y_test, y_pred))

# Save model
joblib.dump(pipeline, BASE_DIR / "intent_pipeline_v1.pkl")

print("Model trained with Lemmatization and Calibration saved.")
