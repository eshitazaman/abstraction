from num2words import num2words

def num_to_camel(n):
    # Get the words from num2words (default is English)
    words = num2words(n)
    # Remove punctuation and split into words
    parts = words.replace('-', ' ').replace(',', '').split()
    # Convert to camelCase or PascalCase
    return parts[0].lower() + ''.join(word.capitalize() for word in parts[1:])

def repeat_with_dots(s, k) :
    return ".".join([s] * k)

def preamble(doors):

    result  = "plts:\n"
    result += "    formula launch   = (s=0)\n"
    result += "                     & (c=0)"

    for door in range(1,doors+1):
        result += f"\n                     & (v{door}=0)"
    
    result += ";\n"

    return result

def init(doors):

    result  = f"\n    formula complete = (c>={doors//2});\n"
    result += "\n"
    result += "    module plts\n"
    result += f"        s  : [0..{doors}];\n"
    result += f"        c  : [0..{doors}];\n"
    
    for door in range(1,doors+1):
        result += f"        v{door} : [0..1];\n"

    return result+"\n"

def command(doors, source, target, probability):

    result  = "        "
    result += f"[{num_to_camel(target)}] " # action
    result += f"(s={source}) -> "       # guard
    result += f"{probability:.2f}:(s'={target})&(c'=min({doors},c+(1-v{target})))&(v{target}'=1) + " # prob: update
    result += f"{(1-probability):.2f}:(s'={target})&(c'=c)&(v{target}'=1);\n" # prob: update

    return result

def epilogue():

    result  = "    endmodule\n"
    result += "endplts\n\n"

    return result

def plts(doors,probabilities):

    result  = preamble(doors)

    result += init(doors)

    result += f"{command(doors,source=0,target=1,probability=probabilities[1])}"
    result += f"{command(doors,source=0,target=2,probability=probabilities[2])}"

    result += f"{command(doors,source=1,target=2,probability=probabilities[2])}"
    result += f"{command(doors,source=1,target=3,probability=probabilities[3])}"

    result += f"{command(doors,source=2,target=1,probability=probabilities[1])}"
    result += f"{command(doors,source=2,target=4,probability=probabilities[4])}"

    for door in range(3,doors-1):

        target  = door-2
        result += f"{command(doors,source=door,target=target,probability=probabilities[target])}"

        target  = door + (1 if (door % 2) else -1)
        result += f"{command(doors,source=door,target=target,probability=probabilities[target])}"

        target  = door+2
        result += f"{command(doors,source=door,target=target,probability=probabilities[target])}"

    source, target  = doors-1, doors-3
    result += f"{command(doors,source,target,probability=probabilities[target])}"

    target  = doors
    result += f"{command(doors,source,target,probability=probabilities[target])}"

    source, target  = doors, doors-2
    result += f"{command(doors,source,target,probability=probabilities[target])}"

    target  = doors-1
    result += f"{command(doors,source,target,probability=probabilities[target])}"

    result += epilogue()

    return result

def kh(success):

    result  = f"property : Kh(launch,complete) >= {success}\n"
    result += f"endproperty\n"

    return result

def salon(doors):

    result = ""

    path  = [ num_to_camel(door) for door in range(1,doors+1,2) ]
    path += [ num_to_camel(door) for door in reversed(range(2,doors+1,2)) ]

    result  = "("+".".join(path)+")*+("+".".join(reversed(path))+")*"

    return result

def canyengue(doors, k):

    result = []
    for door in range(1,doors,2):
        #result += [f"(({num_to_camel(door)}.{num_to_camel(door+1)})*+({num_to_camel(door+1)}.{num_to_camel(door)})*)"]
        result += [f"""(({repeat_with_dots(f"{num_to_camel(door)}.{num_to_camel(door+1)}", k)})+({repeat_with_dots(f"{num_to_camel(door+1)}.{num_to_camel(door)}", k)}))"""]
       
    result  = ".".join(result)

    return result

def milonga(doors):

    result = ""

    path   = ["one"]
    flip   = 1
    room   = 1

    for cursor in range(0,doors-1):
        room += 2 if (cursor % 2) else flip
        path += [f"{num_to_camel(room)}"]
        flip  = (-1*flip) if (cursor % 2) else flip
    
    result  = "("+".".join(path)+")+"

    path   = ["two"]
    flip   = -1
    room   = 2

    for cursor in range(0,doors-1):
        room += 2 if (cursor % 2) else flip
        path += [f"{num_to_camel(room)}"]
        flip  = (-1*flip) if (cursor % 2) else flip

    result  += "("+".".join(path)+")"

    return result

def perception(doors, mode, k=4):
    """
        A function to generate the perception, the k parameter is for canyengue
    """
    result  = "perception :\n    "

    if mode == "canyengue":
        result += canyengue(doors, k)
    elif mode == "salon":
        result += salon(doors)
    elif mode == "milonga":
        result += milonga(doors)

    result += "\nendperception\n\n"

    return result