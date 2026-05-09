import subprocess
import os
import csv

if __name__ == "__main__" :
    result = {}
    modes = ["canyengue", "salon", "milonga"]
    result = [] # the result is a list of dics, each dict is a row
    for mode in modes :
        for file in os.listdir(f"../benchmark/{mode}") :
            row = {}
            row["mode"] = mode
            instance = file.replace(".kr","").split('-')
            row["prob"] = instance[2]
            row["rooms"] = instance[1]
            if mode == "canyengue" :
                row["k"] = instance[3]
            instance_path = os.path.join(f"../benchmark/{mode}", file)
            print(f"Ejecutando: python -i akr.py {instance_path}")
            try :
                output = subprocess.run(["python", "../../../src/akr.py", "-i", instance_path], capture_output=True).stdout.decode()
                lines = output.splitlines()
                for line in lines :
                    if line.startswith("Time") :
                        row["time"] = line.split()[1]
                    elif line.startswith("Maximum number of states") :
                        row["states"] = line.split()[4]
                    elif line.startswith("Maximum number of trans") :
                        row["trans"] = line.split()[4]
                    elif line.startswith("The property is:") :
                        row["result"] = line.split()[3]
            except Exception as e:
                print(f'Error ejecutando {instance_path}:'+str(e))
            result.append(row)

    fieldnames = result[0].keys()

    # Write to CSV
    with open("output.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()     # write header row
        writer.writerows(result)   # write data rows

