INTERESTING_FILE = "db/interesting.txt"

def load_rules():
    operators = set()
    types = set()
    regs = set()

    try:
        with open(INTERESTING_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                line = line.upper()

                if line.startswith("OP:"):
                    operators.add(line[3:].strip())
                elif line.startswith("TYPE:"):
                    types.add(line[5:].strip())
                elif line.startswith("REG:"):
                    regs.add(line[4:].strip())
    except:
        pass

    return {
        "operators": operators,
        "types": types,
        "regs": regs,
    }

def is_interesting(info, rules):
    reg = info["registration"].upper()
    typecode = info["typecode"].upper()
    operator = info["operator"].upper()

    return (
        any(op in operator for op in rules["operators"])
        or any(t in typecode for t in rules["types"])
        or any(r in reg for r in rules["regs"])
    )