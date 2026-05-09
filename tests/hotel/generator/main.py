import sys
from sys import argv
from num2words import num2words
from uplts import plts, perception, kh 
import pathlib # for managing paths


if __name__ == '__main__':
    doors         = len(argv)-4
    if doors < 4 :
        print("Error: the number of doors have to be greater than 3")
        print(f'  use: {argv[0]} <success:float> <prob1:float> <prob2:float> ... <probn:float> canyengue|salon|milonga')
        sys.exit(1) # Exit with an error code

    probabilities = list(map(float, argv[1:-2]))
    mode          = argv[-2]
    

    if doors > 0:
        if mode == "canyengue" :
            for k in [2,4,6,8] :
                fname = f'{mode}-{doors}-{probabilities[0]}-{k}.kr'
                path  = pathlib.Path(argv[-1]+"/"+fname)
                with path.open(mode="w", encoding="utf-8") as ffile:
                    ffile.write(f"{plts(doors,probabilities)}")
                    ffile.write(f"{perception(doors,mode,k)}")
                    ffile.write(f"{kh(success=probabilities[0])}")
        else :
            fname = f'{mode}-{doors}-{probabilities[0]}.kr'
            path  = pathlib.Path(argv[-1]+"/"+fname)
            with path.open(mode="w", encoding="utf-8") as ffile:
                ffile.write(f"{plts(doors,probabilities)}")
                ffile.write(f"{perception(doors,mode)}")
                ffile.write(f"{kh(success=probabilities[0])}")
#        try:
#           ffile = open(fname,'x')
#
#            ffile.write(f"{plts(doors,probabilities)}")
#            ffile.write(f"{perception(doors,mode)}")
#            ffile.write(f"{kh(success=probabilities[0])}")

#        except FileExistsError:
 #           print(f'the file {fname} already exists')

    else:
        print(f'error: incorrect number of arguments for {argv[0]}')
        print(f'  use: {argv[0]} <success:float> <prob1:float> <prob2:float> ... <probn:float> canyengue|salon|milonga')

