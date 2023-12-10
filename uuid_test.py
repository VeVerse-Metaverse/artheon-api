import shortuuid

generated = []
collisions = 0


def func():
    global collisions
    g = shortuuid.uuid()[:5].upper()
    if g in generated:
        collisions += 1
    else:
        generated.append(g)
    return g


total = 100000
for i in range(0, total):
    g = func()
    if i % 10000 == 0:
        print(f"{i}: {g}")

print(f"{collisions}, rate {(collisions / total) * 100}%")
