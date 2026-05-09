# Generator for UPLTS Test Cases

This folder contains a script for generating **Uncertainty-based Probabilistic Labeled Transition Systems (UPLTSs)** corresponding to the hotel layout presented in the paper. The script also encodes the various paths (perceptions) the cleaning robot may follow when attempting to service rooms without disturbing guests.

---

## Usage

```bash
python <path-to-generator>/generator/main.py <success> <prob1> <prob2> ... <probn> canyengue|salon|milonga
```

---

## Parameters

- **`<success>`**  
  The probability threshold for the knowing-how property to check:  
  ```
  Kh(launch, complete) >= success
  ```
  This formula expresses that the robot (*tango*) can successfully clean at least half of the rooms on a floor.

- **`<probi>`**  
  The probability that room *i* does **not** have a "do not disturb" sign.  
  Equivalently, the probability that the robot can enter and clean room *i*.  
  Assumption: the number of rooms **n ≥ 4**.

- **`canyengue|salon|milonga`**  
  The perception (strategy or path) the robot considers while cleaning.  
  The names are a nod to tango dance styles.

---

## Hotel Layout

Rooms are arranged in pairs along a hallway as shown below:

```
+----+----+----+----+----+----+
|  1 |  3 |  5 |  7 |  9 | ...|
+----+----+----+----+----+----+
+----+----+----+----+----+----+
|  2 |  4 |  6 |  8 | 10 | ...|
+----+----+----+----+----+----+
```

- Odd-numbered rooms are on the top row (left side of the hallway).  
- Even-numbered rooms are on the bottom row (right side of the hallway).  

---

## Perceptions

The robot's strategies are represented by regular patterns:

- **Canyengue**  
  ```
  ((1.2)* + (2.1)*).((2.3)* + (3.2)*).((4.5)* + (5.4)*). ... .(((n-1).n)* + (n.(n-1))*)
  ```
  **Visualization (example with 6 rooms):**  
  ```
  1 <-> 2   3 <-> 4   5 <-> 6 
  ```

- **Salon**  
  ```
  (1.3.5.7. ... .(n-1).n. ... .8.6.4.2)* + (2.4.6.8. ... .n.(n-1). ... .7.5.3.1)*
  ```
  **Visualization (example with 6 rooms):**  
  ```
  1 → 3 → 5 → 6 → 4 → 2 → repeat
  or
  2 → 4 → 6 → 5 → 3 → 1 → repeat
  ```

- **Milonga**  
  ```
  (1.2.4.3.5.7.6.8. ... .(n-1).n) + (2.1.3.4.6.5.7.8. ... .n.(n-1))
  ```
  **Visualization (example with 6 rooms):**  
  ```
  1 → 2 → 4 → 3 → 5 → 6
  or
  2 → 1 → 3 → 4 → 6 → 5
  ```

---

## Example

Generate a UPLTS with 6 rooms, where the success threshold is `0.1`, the probability of each room being serviceable is `0.8`, and the perception is *salon*:

```bash
python generator/main.py 0.1 0.8 0.8 0.8 0.8 0.8 0.8 salon
```

---

## Notes

- The script assumes that once a room's status is determined (serviceable or not), it remains fixed for the run.  
- Cleaning the same room multiple times only counts once toward the total.  
- The generated UPLTSs are consistent with the semantics described in the paper.
