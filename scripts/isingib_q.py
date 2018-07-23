import matplotlib.pyplot as plt
import numpy as np

from information_bottleneck_q import *
from ising_iterator import *

# parameters #
##############

perform_beta_sweep = False
perform_demo = True

symmetrize = True

sz = 81     # size of the samples (sq)
vsz = 3   # size of visible block (sq)
edist = 4   # distance to environment patch
tsz = 1000000   # table size
dfile = '/Users/andrew/Documents/rgml/ising_data/data_0_45'
savefile = "/Users/andrew/Documents/rgml/ip_data/strawberry/isingib_q_joint_%02d.npy" % edist
# savefile = "isingib_q_joint_%02d.npy" % edist

# load data #
#############


def to_code(spins):
    ret = 0
    for i, j in enumerate(spins):
        j = 1 if j == 1 else 0
        ret += j << i

    return ret


def calculate_joint(eloc):
    """
    Calculates the joint p(x,x')
    """
    thist = np.zeros((2**(vsz**2), 2**(vsz**2)))

    for _, sample in zip(range(tsz), IsingIterator(dfile, img_size=sz)):
        vcode = to_code(np.reshape(sample[0:vsz, 0:vsz], -1))
        ecode = to_code(np.reshape(sample[eloc:eloc+vsz, eloc:eloc+vsz], -1))

        thist[vcode, ecode] += 1

    thist /= tsz

    return thist


# calculate and store if necessary #
####################################

try:
    joint_file = open(savefile, 'rb')
except IOError:
    print("Computing new joint distribution")
    thist = calculate_joint(edist)
    joint_file = open(savefile, 'wb')
    np.save(joint_file, thist)
else:
    print("Loading saved joint distribution")
    thist = np.load(joint_file)

# information bottleneck test #
###############################
if symmetrize:
    thist = (thist + thist.T)/2

if perform_demo:
    dib = DIB(thist, beta=20, hiddens=100)
    dib.compress()
    dib.report_clusters()
    c = dib.visualize_clusters(debug=True)

# beta sweep #
##############

if perform_beta_sweep:
    betas = np.arange(0, 80.1, 1.0)
    hiddens = 100
    info_y = np.zeros_like(betas, dtype=np.float32)
    info_x = np.zeros_like(betas, dtype=np.float32)
    clusters = {x: [] for x in range(1, hiddens)}
    clusters2 = np.zeros_like(betas, dtype=np.uint8)
    clusterings = {}

    for i, beta in enumerate(betas):
        dib = DIB(thist, beta=beta, hiddens=hiddens)
        dib.compress()
        f = dib.report_clusters()
        info_y[i] = dib.mi_relevant()
        info_x[i] = dib.mi_captured()
        clusters[np.unique(f).size].append(beta)
        clusters2[i] = np.unique(f).size
        clusterings[beta] = dib.f

    # calculate kink angles
    angles = {k: np.pi/2 - np.arctan(np.min(v + [1e3])) -
              np.arctan(1/np.max(v + [1e-3]))
              for k, v in clusters.items()}
    angles = {k: v * 180/np.pi for k, v in angles.items()}
    angles = {k: max(v, 0) for k, v in angles.items()}

    plt.plot(info_x, info_y, 'ko')
    plt.title('DIB Plane Plot')
    plt.xlabel('H(T)')
    plt.ylabel('I(Y;T)')
    plt.show()

    with open("ipdata_%02d.pkl" % edist, 'wb') as f:
        dump = {}
        dump['info_x'] = info_x
        dump['info_y'] = info_y
        dump['angles'] = angles
        dump['betas'] = betas
        dump['clusters'] = clusters
        dump['clusters2'] = clusters2
        dump['clusterings'] = clusterings
        dump['theta'] = np.array([angles[k] for k in clusters])
        pickle.dump(dump, f)
