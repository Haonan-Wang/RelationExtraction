import os
import sys
import errno

from stanfordnlp.server import CoreNLPClient


class RelationExtractor:
    def __init__(self, corenlp_home, endpoint='http://localhost:9000', timeout=15000, memory='2G'):
        print('Set up Stanford CoreNLP Server.')

        if os.path.exists(corenlp_home):
            os.environ['CORENLP_HOME'] = corenlp_home
        else:
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), corenlp_home)

        self.client = CoreNLPClient(annotators=['depparse'], endpoint=endpoint, timeout=timeout, memory=memory)
        self.client.annotate('Prepare.')

    def extract(self, text):
        """
        extract relations from text.

        params:
            text: string

        return:
            sentences: [sentence]

            --format--
            sentence: {
                'tokens': [word],
                'relations': [(subject word index, (predicate word index), object word index)]
            }
            word: string
            word index: int
        """
        ann = self.client.annotate(text)

        sentences = []
        for sentence in ann.sentence:
            # extract relations from sentence
            relations = self._extract_by_subj_obj(sentence) + self._extract_by_nmod(sentence)
            # deal with "of" dependency such as "a group of people", replace "group" with "people" in relations
            relations = self._replace_by_of(sentence, relations)

            sentences.append({
                'tokens': [token.word for token in sentence.token],
                'relations': relations
            })
        return sentences

    def _extract_by_subj_obj(self, sentence):
        """
        extract action/verb relations by "nsubj"/"acl" and "dobj"/"acl:relcl" dependency.

        return:
            relations: [(subject word index, (predicate word index), object word index)]
        """
        edges = sentence.enhancedPlusPlusDependencies.edge

        pred2insts = {}
        for edge in edges:
            subj, pred, obj = None, None, None
            if edge.dep == 'nsubj':
                subj, pred = edge.target, edge.source
            elif edge.dep == 'acl':
                subj, pred = edge.source, edge.target
            elif edge.dep == 'dobj':
                pred, obj = edge.source, edge.target
            elif edge.dep == 'acl:relcl':
                pred, obj = edge.target, edge.source
            else:
                continue

            if pred not in pred2insts:
                pred2insts[pred] = {
                    'subjs': [],
                    'objs': []
                }

            if subj is None:
                pred2insts[pred]['objs'].append(obj)
            else:
                pred2insts[pred]['subjs'].append(subj)

        relations = []
        for pred in pred2insts:
            insts = pred2insts[pred]
            for subj in insts['subjs']:
                for obj in insts['objs']:
                    relations.append((subj - 1, tuple([pred - 1]), obj - 1))

        return relations

    def _extract_by_nmod(self, sentence):
        """
        extract preposition/preposition phrase and spatial relations by "nmod" dependency.

        return:
            relations: [(subject word index, (predicate word index), object word index)]
        """
        edges = sentence.enhancedPlusPlusDependencies.edge

        # case: to find preposition index in tokens
        # mew: to concatenate preposition phrase, such as "in front of"
        # acl/nsubj: to concatenate verb and preposition phrase, such as "park in front of"
        # and: to expand relations by parallel subjects/objects
        dep_idx = {dep: {} for dep in ['case', 'mwe', 'acl', 'nsubj', 'conj:and']}
        for edge in edges:
            if edge.dep not in dep_idx:
                continue

            source, target = edge.source, edge.target
            if edge.dep == 'acl':
                source, target = target, source

            if source not in dep_idx[edge.dep]:
                dep_idx[edge.dep][source] = []
            dep_idx[edge.dep][source].append(target)

        # exclude relations with "of", "for"......
        exclude = ['of', 'for']

        relations = []
        for edge in edges:
            if not edge.dep.startswith('nmod:'):
                continue

            nmod = edge.dep[5:]
            if nmod in exclude:
                continue

            # target should be noun
            if not sentence.token[edge.target - 1].pos.startswith('NN'):
                continue

            # find preposition indice
            if edge.target not in dep_idx['case']:
                continue
            pred = None
            for case in dep_idx['case'][edge.target]:
                word_idc = [case]
                word = sentence.token[case - 1].word
                if case in dep_idx['mwe']:
                    word_idc.extend(dep_idx['mwe'][case])
                    word = '_'.join([sentence.token[idx - 1].word for idx in word_idc])
                if word == nmod:
                    pred = word_idc
                    break
            if pred is None:
                continue

            if sentence.token[edge.source - 1].pos.startswith('NN'):
                # add preposition relations
                relations.append((edge.source, tuple(pred), edge.target))
            else:
                # add preposition phrase relations
                for dep in ['acl', 'nsubj']:
                    if edge.source in dep_idx[dep]:
                        if edge.source + 1 == pred[0]:
                            # concatenate verb and preposition phrase
                            pred.insert(0, edge.source)
                        relations.extend([(source, tuple(pred), edge.target) for source in dep_idx[dep][edge.source]])
                        break

        # expand relations
        expanded_relations = set()
        for relation in relations:
            subj, pred, obj = relation

            equal_insts = {
                'subjs': [subj],
                'objs': [obj]
            }
            for typ in equal_insts:
                inst = equal_insts[typ][0]
                if inst in dep_idx['conj:and']:
                    equal_insts[typ].extend(dep_idx['conj:and'][inst])

            pred = tuple([idx - 1 for idx in pred])
            for subj in equal_insts['subjs']:
                for obj in equal_insts['objs']:
                    expanded_relations.add((subj - 1, pred, obj - 1))

        return list(expanded_relations)

    def _replace_by_of(self, sentence, relations):
        """
        deal with "of" dependency such as "a group of people", replace "group" with "people" in relations

        return:
            relations: [(subject word index, (predicate word index), object word index)]
        """
        edges = sentence.enhancedPlusPlusDependencies.edge

        of_idx = {}
        for edge in edges:
            if edge.dep == 'nmod:of':
                if edge.source - 1 not in of_idx:
                    of_idx[edge.source - 1] = []
                of_idx[edge.source - 1].append(edge.target - 1)

        relpaced_relations = set()
        for relation in relations:
            subj, pred, obj = relation

            real_insts = {
                'subjs': [subj],
                'objs': [obj]
            }
            for typ in real_insts:
                inst = real_insts[typ][0]
                if inst in of_idx:
                    real_insts[typ] = of_idx[inst]

            for subj in real_insts['subjs']:
                for obj in real_insts['objs']:
                    relpaced_relations.add((subj, pred, obj))

        return list(relpaced_relations)


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        corenlp_home, text = sys.argv[1:3]

        relationExtractor = RelationExtractor(corenlp_home)
        sentences = relationExtractor.extract(text)

        print('\ntext:', text)
        for num, sentence in enumerate(sentences):
            tokens = sentence['tokens']
            print('\nsentence', num + 1)
            print('-tokens:', tokens)

            print('-relations:')
            for relation in sentence['relations']:
                subj = tokens[relation[0]]
                pred = '-'.join([tokens[idx] for idx in relation[1]])
                obj = tokens[relation[2]]
                print(relation, '->', (subj, pred, obj))
    else:
        print('Usage: python relation.py "corenlp_home" "text"')
