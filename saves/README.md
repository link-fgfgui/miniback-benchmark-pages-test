# Drop progressive full saves here

One directory or archive per restore point, ordered by filename (natural sort):

    saves/01-world/          world root, or a directory containing world/
    saves/02-world.tar.gz
    saves/03-world/

Then run:

    ./bench.py run --saves saves --levels 3,9 --long off,on
