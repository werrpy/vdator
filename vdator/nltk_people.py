import nltk
from nltk.corpus import stopwords

# download nltk resources
ntlk_list = [
    "stopwords",
    "punkt",
    "averaged_perceptron_tagger",
    "maxent_ne_chunker",
    "words",
]
for t in ntlk_list:
    nltk.download(t)

stop = stopwords.words("english")


def ie_preprocess(document):
    """
    nltk preprocess text

    Parameters
    ----------
    document : str
        text to pre process

    Returns
    -------
    list sentences
    """
    document = " ".join([i for i in document.split() if i not in stop])
    sentences = nltk.sent_tokenize(document)
    sentences = [nltk.word_tokenize(sent) for sent in sentences]
    sentences = [nltk.pos_tag(sent) for sent in sentences]
    return sentences


def extract_names(document):
    """
    nltk extract person names

    Parameters
    ----------
    document : str
        text

    Returns
    -------
    list person names
    """
    names = []
    sentences = ie_preprocess(document)
    for tagged_sentence in sentences:
        for chunk in nltk.ne_chunk(tagged_sentence):
            if type(chunk) == nltk.tree.Tree:
                if chunk.label() == "PERSON":
                    names.append(" ".join([c[0] for c in chunk]))
    return names
