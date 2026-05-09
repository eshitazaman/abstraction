# A simple script to generate the benchmark
import subprocess
import random
# modes: canyengue|salon|milonga
canyengueNumber = 50 # number of examples
salonNumber = 50 # number of examples
milongaNumber = 50 # number of examples 

if __name__ == "__main__" :
    insNumber = {}
    insNumber["canyengue"] = [i*2 for i in range(canyengueNumber) if i >= 2]
    insNumber["salon"] = [i*2 for i in range(salonNumber) if i >= 2]
    insNumber["milonga"] = [i*2 for i in range(milongaNumber) if i >= 2]    
    # we generate the examples for tango

    for mode in ["canyengue", "salon", "milonga"] :
        print(f"Generating {mode} files.")
        for prob in [0.25,0.50, 0.75] : # for these probs
            for i in insNumber[mode] :
                doorProbs = [str(random.random()) for _ in range(i)] 
                parameters = ["python", "main.py", str(prob)] + doorProbs + [mode] + [f"../benchmark/{mode}"]
                try :
                    result = subprocess.run(parameters, capture_output=True, text=True, check=True)
                except Exception as e:
                    print(f"Error Generating File: {e}")
    


