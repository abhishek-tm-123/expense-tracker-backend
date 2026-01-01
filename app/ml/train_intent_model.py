import pandas as pd
import joblib

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# Load data
df = pd.read_csv("intent_dataset.csv")

X = df["text"]
y = df["intent"]

# Pipeline (THIS MATTERS)
pipeline = Pipeline([
    (
        "vectorizer",
        TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),   # BIG DEAL
            min_df=1,
            max_df=0.9
        )
    ),
    (
        "clf",
        LogisticRegression(
            max_iter=1000,
            class_weight="balanced"  # IMPORTANT
        )
    )
])

# Train-test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

pipeline.fit(X_train, y_train)

# Evaluate
y_pred = pipeline.predict(X_test)
print(classification_report(y_test, y_pred))

# Save model + vectorizer
joblib.dump(pipeline.named_steps["clf"], "intent_model.pkl")
joblib.dump(pipeline.named_steps["vectorizer"], "vectorizer.pkl")

print("✅ Model trained and saved")
