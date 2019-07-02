import sys
sys.path.append("../figures")

from where_copie import RetinaTransform, WhereNet, CollTransform, MNIST, Normalize, WhereTrainer, Where

import datetime

from main import init
args = init(filename='../data/2019-06-12')

args.epochs = 60
args.save_model = True

where = Where(args)

acc = where.test()

print("acc = ", acc)

print(datetime.datetime.now())