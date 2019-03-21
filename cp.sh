for file in annotation/*/marina.tsv
do
    dir=$(basename $(dirname $file))
    cp $file $dir
done
