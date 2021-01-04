from pydash import has
import difflib


def balanced_blockquotes(str):
    num_blockquotes = str.count("```")
    # balanced if even number of blockquotes
    return (num_blockquotes % 2) == 0


def split_string(str, limit, sep="\n"):
    limit = int(limit)
    words = str.split(sep)

    if max(map(len, words)) > limit:
        # limit is too small, return original string
        return str

    res, part, others = [], words[0], words[1:]
    for word in others:
        if (len(sep) + len(word)) > (limit - len(part)):
            res.append(part)
            part = word
        else:
            part += sep + word
    if part:
        res.append(part)

    return res


def has_many(obj, base, keys):
    for key in keys:
        lookup = ""
        if base:
            lookup += base + "."
        lookup += key
        if not has(obj, lookup):
            return False
    return True


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def num_to_emoji(n):
    num_emoji_map = {
        "1": ":one:",
        "2": ":two:",
        "3": ":three:",
        "4": ":four:",
        "5": ":five:",
        "6": ":six:",
        "7": ":seven:",
        "8": ":eight:",
        "9": ":nine:",
        "10": ":ten:",
    }

    n = str(n)
    if n in num_emoji_map:
        return num_emoji_map[n]
    return False


def show_diff(expected, actual):
    seqm = difflib.SequenceMatcher(None, expected, actual)

    output = []
    for opcode, a0, a1, b0, b1 in seqm.get_opcodes():
        if opcode == "equal":
            output.append(seqm.a[a0:a1])
        elif opcode == "insert":
            output.append("**" + seqm.b[b0:b1] + "**")
        elif opcode == "delete":
            output.append("**" + seqm.a[a0:a1] + "**")
        elif opcode == "replace":
            output.append("**" + seqm.a[a0:a1] + "**")
        else:
            # unexpected opcode
            return False
    return "Hint: " + "".join(output) + "\n"
