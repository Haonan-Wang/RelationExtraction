# RelationExtraction

## Dependency

- Python 3.6+
- pip install stanfordnlp
- Java 1.8+
- Stanford CoreNLP
  
  Click [here](http://nlp.stanford.edu/software/stanford-corenlp-full-2018-10-05.zip) to download "stanford-corenlp-full-*.zip", unzip it to any location.

## Usage

python relation.py "/path/to/stanford-corenlp-full-*" "text to extract relations"

## Example

**input:**<br>
Boys and girls play ball next to a tree. And a man takes a picture.

**output:**<br>
sentence 1<br>
-tokens: ['Boys', 'and', 'girls', 'play', 'ball', 'next', 'to', 'a', 'tree', '.']<br>
-relations:<br>
(0, (3,), 4) -> ('Boys', 'play', 'ball')<br>
(2, (3,), 4) -> ('girls', 'play', 'ball')<br>
(2, (5, 6), 8) -> ('girls', 'next-to', 'tree')<br>
(0, (5, 6), 8) -> ('Boys', 'next-to', 'tree')

sentence 2<br>
-tokens: ['And', 'a', 'man', 'takes', 'a', 'picture', '.']<br>
-relations:<br>
(2, (3,), 5) -> ('man', 'takes', 'picture')