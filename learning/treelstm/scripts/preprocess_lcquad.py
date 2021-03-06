"""
Preprocessing script for LC-Quad data.

"""

import os
import glob
import json
import anytree
from tqdm import tqdm
from common.utility.utility import find_mentions
from parser.lc_quad_linked import LC_Qaud_LinkedParser


def make_dirs(dirs):
    for d in dirs:
        if not os.path.exists(d):
            os.makedirs(d)


def dependency_parse(filepath, cp='', tokenize=True):
    print('\nDependency parsing ' + filepath)
    dirpath = os.path.dirname(filepath)
    filepre = os.path.splitext(os.path.basename(filepath))[0]
    tokpath = os.path.join(dirpath, filepre + '.toks')
    parentpath = os.path.join(dirpath, filepre + '.parents')
    relpath = os.path.join(dirpath, filepre + '.rels')
    tokenize_flag = '-tokenize - ' if tokenize else ''
    cmd = ('java -cp %s DependencyParse -tokpath %s -parentpath %s -relpath %s %s < %s'
           % (cp, tokpath, parentpath, relpath, tokenize_flag, filepath))
    os.system(cmd)


# def constituency_parse(filepath, cp='', tokenize=True):
#     dirpath = os.path.dirname(filepath)
#     filepre = os.path.splitext(os.path.basename(filepath))[0]
#     tokpath = os.path.join(dirpath, filepre + '.toks')
#     parentpath = os.path.join(dirpath, filepre + '.cparents')
#     tokenize_flag = '-tokenize - ' if tokenize else ''
#     cmd = ('java -cp %s ConstituencyParse -tokpath %s -parentpath %s %s < %s'
#            % (cp, tokpath, parentpath, tokenize_flag, filepath))
#     os.system(cmd)


def query_parse(filepath):
    dirpath = os.path.dirname(filepath)
    filepre = os.path.splitext(os.path.basename(filepath))[0]
    tokpath = os.path.join(dirpath, filepre + '.toks')
    parentpath = os.path.join(dirpath, filepre + '.parents')
    with open(filepath) as datafile, \
            open(tokpath, 'w') as tokfile, \
            open(parentpath, 'w') as parentfile:
        for line in tqdm(datafile):
            clauses = line.split(" .")
            vars = dict()
            root = None
            for clause in clauses:
                triple = [item.replace("\n", "") for item in clause.split(" ")]

                root_node = anytree.Node(triple[1])
                left_node = anytree.Node(triple[0], root_node)
                right_node = anytree.Node(triple[2], root_node)

                leveled = [left_node, root_node, right_node]
                for item in triple:
                    if item.startswith("?u_"):
                        if item in vars:
                            children = vars[item].parent.children
                            if children[0] == vars[item]:
                                vars[item].parent.children = [root_node, children[1]]
                            else:
                                vars[item].parent.children = [children[0], root_node]
                            vars[item] = [node for node in leveled if node.name == item][0]
                            break
                        else:
                            vars[item] = [node for node in leveled if node.name == item][0]

                if root is None:
                    root = root_node

            pre_order = [node for node in anytree.iterators.PreOrderIter(root)]
            tokens = [node.name for node in pre_order]
            for i in range(len(pre_order)):
                pre_order[i].index = i + 1
            idxs = [node.parent.index if node.parent is not None else 0 for node in pre_order]

            tokfile.write(" ".join(tokens) + "\n")
            parentfile.write(" ".join(map(str, idxs)) + "\n")


def build_vocab(filepaths, dst_path, lowercase=True):
    vocab = set()
    for filepath in filepaths:
        with open(filepath) as f:
            for line in f:
                if lowercase:
                    line = line.lower()
                vocab |= set(line.split())
    with open(dst_path, 'w') as f:
        for w in sorted(vocab):
            f.write(w + '\n')


def generalize_question(a, b, parser=None):
    # replace entity mention in question with a generic symbol

    if parser is None:
        parser = LC_Qaud_LinkedParser()

    _, _, uris = parser.parse_sparql(b)
    uris = [uri for uri in uris if uri.is_entity()]

    i = 0
    for item in find_mentions(a, uris):
        a = "{} #en{} {}".format(a[:item["start"]], "t" * (i + 1), a[item["end"]:])
        b = b.replace(item["uri"].raw_uri, "#en{}".format("t" * (i + 1)))

    # remove extra info from the relation's uri and remaining entities
    for item in ["http://dbpedia.org/resource/", "http://dbpedia.org/ontology/",
                 "http://dbpedia.org/property/", "http://www.w3.org/1999/02/22-rdf-syntax-ns#"]:
        b = b.replace(item, "")
    b = b.replace("<", "").replace(">", "")

    return a, b


def split(data, parser=None):
    if isinstance(data, str):
        with open(data) as datafile:
            dataset = json.load(datafile)
    else:
        dataset = data

    a_list = []
    b_list = []
    id_list = []
    sim_list = []
    for item in tqdm(dataset):
        i = item["id"]
        a = item["question"]
        for query in item["generated_queries"]:
            a, b = generalize_question(a, query["query"], parser)

            # Empty query should be ignored
            if len(b) < 5:
                continue
            sim = str(2 if query["correct"] else 1)

            id_list.append(i + '\n')
            a_list.append(a.encode('ascii', 'ignore').decode('ascii') + '\n')
            b_list.append(b.encode('ascii', 'ignore').decode('ascii') + '\n')
            sim_list.append(sim + '\n')
    return a_list, b_list, id_list, sim_list


def save_split(dst_dir, a_list, b_list, id_list, sim_list):
    with open(os.path.join(dst_dir, 'a.txt'), 'w') as afile, \
            open(os.path.join(dst_dir, 'b.txt'), 'w') as bfile, \
            open(os.path.join(dst_dir, 'id.txt'), 'w') as idfile, \
            open(os.path.join(dst_dir, 'sim.txt'), 'w') as simfile:
        for i in range(len(a_list)):
            idfile.write(id_list[i])
            afile.write(a_list[i])
            bfile.write(b_list[i])
            simfile.write(sim_list[i])


def parse(dirpath, cp='', dep_parse=True):
    if dep_parse:
        dependency_parse(os.path.join(dirpath, 'a.txt'), cp=cp, tokenize=True)
    # constituency_parse(os.path.join(dirpath, 'a.txt'), cp=cp, tokenize=True)
    query_parse(os.path.join(dirpath, 'b.txt'))


if __name__ == '__main__':
    print('=' * 80)
    print('Preprocessing LC-Quad dataset')
    print('=' * 80)

    base_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    data_dir = os.path.join(base_dir, 'data')
    lc_quad_dir = os.path.join(data_dir, 'lc_quad_gold')
    lib_dir = os.path.join(base_dir, 'lib')
    train_dir = os.path.join(lc_quad_dir, 'train')
    dev_dir = os.path.join(lc_quad_dir, 'dev')
    test_dir = os.path.join(lc_quad_dir, 'test')
    make_dirs([train_dir, dev_dir, test_dir])

    # java classpath for calling Stanford parser
    classpath = ':'.join([
        lib_dir,
        os.path.join(lib_dir, 'stanford-parser/stanford-parser.jar'),
        os.path.join(lib_dir, 'stanford-parser/stanford-parser-3.5.1-models.jar')])

    # split into separate files
    train_filepath = os.path.join(lc_quad_dir, 'LCQuad_train.json')
    trail_filepath = os.path.join(lc_quad_dir, 'LCQuad_trial.json')
    test_filepath = os.path.join(lc_quad_dir, 'LCQuad_test.json')

    ds = json.load(open("../../../output/lc_quad_gold.json"))
    total = len(ds)
    train_size = int(.7 * total)
    dev_size = int(.2 * total)
    test_size = int(.1 * total)

    json.dump(ds[:train_size], open(train_filepath, "w"))
    json.dump(ds[train_size:train_size + dev_size], open(trail_filepath, "w"))
    json.dump(ds[train_size + dev_size:], open(test_filepath, "w"))

    parser = LC_Qaud_LinkedParser()

    print('Split train set')
    save_split(train_dir, *split(train_filepath, parser))
    print('Split dev set')
    save_split(dev_dir, *split(trail_filepath, parser))
    print('Split test set')
    save_split(test_dir, *split(test_filepath, parser))

    # parse sentences
    print("parse train set")
    parse(train_dir, cp=classpath)
    print("parse dev set")
    parse(dev_dir, cp=classpath)
    print("parse test set")
    parse(test_dir, cp=classpath)

    # get vocabulary
    build_vocab(
        glob.glob(os.path.join(lc_quad_dir, '*/*.toks')),
        os.path.join(lc_quad_dir, 'vocab.txt'))
    build_vocab(
        glob.glob(os.path.join(lc_quad_dir, '*/*.toks')),
        os.path.join(lc_quad_dir, 'vocab-cased.txt'),
        lowercase=False)
