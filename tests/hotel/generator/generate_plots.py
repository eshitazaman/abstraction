import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def plot1(df) :
    
    fig, ax1 = plt.subplots(figsize=(14, 7))

    # --- Plot Time vs Rooms (primary y-axis) ---
    sns.lineplot(
        data=df, 
        x='rooms', 
        y='time', 
        hue='prob',      # different line for each probability
        dashes=False, 
        ax=ax1
    )
    ax1.set_ylabel('Time', color='blue')
    ax1.set_xlabel('Rooms')
    ax1.tick_params(axis='y', labelcolor='blue')


    plt.title('Time, States, and Transitions vs Rooms (Lines per Probability)')
    ax1.grid(True, linestyle='--', alpha=0.5)
    plt.show()

def plot2 (data) :
    # Plot time vs rooms for each probability
    plt.figure(figsize=(12, 6))
    for p in [0.25,0.5,0.75]:
        subset = milonga[milonga['prob'] == p]
        print(subset['rooms'])
        plt.plot(subset['rooms'], subset['time'], marker='o', label=f'prob={p}')
            # Mark failures
            #failures = subset[subset['result'] == False]
            #plt.scatter(failures['rooms'], failures['time'], color='red', edgecolor='black', s=100, zorder=5, label=f'fail prob={p}')

    plt.xlabel('Number of Rooms')
    plt.ylabel('Verification Time (s)')
    plt.title('Robot Verification Time vs Number of Rooms')
    plt.legend()
    plt.grid(True)
    plt.show()

def basic_plot(df, name) :
    fig = plt.figure(figsize=(12,8))
    ax = fig.add_subplot(111, projection='3d')

    # Define colors for probability
    prob_colors = {0.25: 'blue', 0.50: 'orange', 0.75: 'green'}

    # Plot each probability separately
    for prob in df['prob'].unique():
        subset = df[df['prob'] == prob]
        ax.plot(
            subset['rooms'], 
            subset['time'], 
            subset['states'], 
            marker='o', 
            linestyle='None', 
            label=f'prob={prob}', 
            color=prob_colors[prob]
        )

    ax.set_xlabel('Rooms')
    ax.set_ylabel('Time')
    ax.set_zlabel('States')
    ax.set_title(f'{name}: Time vs Rooms vs States')
    ax.legend()
    #plt.show()
    plt.savefig(f'{name}.jpg')



def plot_canyengue_modes(df) :
    fig = plt.figure(figsize=(12,8))
    ax = fig.add_subplot(111, projection='3d')

    # Define colors for probability
    prob_colors = {2: 'blue', 4: 'orange', 6: 'green', 8 : 'red'}

    # Plot each probability separately
    for k in df['k'].unique():
        subset = df[df['k'] == k]
        ax.plot(
            subset['rooms'], 
            subset['time'], 
            subset['states'], 
            marker='o', 
            linestyle='None', 
            label=f'k={int(k)}', 
            color=prob_colors[k]
        )

    ax.set_xlabel('Rooms')
    ax.set_ylabel('Time')
    ax.set_zlabel('States')
    ax.set_title('Canyengue: Time vs Rooms vs k')
    ax.legend()
    #plt.show()
    plt.savefig('canyengue_k.jpg')

if __name__ == "__main__" :
     # Load the data
    data = pd.read_csv("output.csv")  # or read from a string if you copy it
    for mode in ["milonga", "salon", "canyengue"] :
        mode_df = data[data["mode"]==f"{mode}"]
        mode_df = mode_df.sort_values(by=["rooms","prob"])
        mode_df.drop('k', axis=1)
        basic_plot(mode_df, f"{mode}")

    # we generate the plot for canyengue taking into account the k's
    canyengue = data[data["mode"]=="canyengue"]
    canyengue = canyengue.sort_values(by=["rooms","k"])
    plot_canyengue_modes(canyengue)