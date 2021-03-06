import pickle

import numpy as np
from keras.datasets import cifar10
from keras.layers import Lambda
from sklearn.cluster import KMeans

from parameters import *
from vae_components import *

if __name__ == '__main__':
    # import dataset
    (image_train, label_train), (image_test, label_test) = cifar10.load_data()

    image_train = np.reshape(image_train, [-1, 32, 32, 3])
    image_test = np.reshape(image_test, [-1, 32, 32, 3])
    image_train = image_train.astype('float32') / 255
    image_test = image_test.astype('float32') / 255

    if args.grayscale:
        image_train = np.reshape(
            np.mean(image_train, axis=-1), (-1,) + input_shape)
        image_test = np.reshape(
            np.mean(image_test, axis=-1), (-1,) + input_shape)

    # load patch encoder grid
    enc_rows = 5
    enc_cols = 5

    # initialize
    if args.deterministic:
        image_train_cg = np.zeros((image_train.shape[0], 5, 5, num_clusters))
        image_test_cg = np.zeros((image_test.shape[0], 5, 5, num_clusters))

        eye = np.eye(num_clusters)
    else:
        image_train_cg = np.zeros((image_train.shape[0], 5, 5, latent_dim))
        image_test_cg = np.zeros((image_test.shape[0], 5, 5, latent_dim))

    # coarsegrain
    for r in range(enc_rows):
        for c in range(enc_cols):
            print(r, c)
            inputs = Input(shape=input_shape, name='encoder_input')

            encoder = Patch_Encoder(inputs, r*sz + 1, c*sz + 1, sz,
                                    hidden_dim=hidden_dim,
                                    intermediate_dim=intermediate_dim,
                                    latent_dim=latent_dim)

            if args.deterministic:
                encoder.load_weights("store/penc_cifar_ld%03d_b%03d_r%02d_c%02d_%d.h5" %
                                     (latent_dim, beta, r*sz + 1, c*sz + 1, input_shape[2]))

                latents_train = encoder.predict(
                    np.reshape(
                        image_train, (-1,) + input_shape)
                )[0]

                latents_test = encoder.predict(
                    np.reshape(
                        image_test, (-1,) + input_shape)
                )[0]

                kmeans = KMeans(n_clusters=num_clusters).fit(latents_train)

                image_train_cg[:, r, c, :] = eye[kmeans.labels_]
                image_test_cg[:, r, c, :] = eye[kmeans.predict(latents_test)]
            else:
                image_train_cg[:, r, c, :] = encoder.predict(
                    np.reshape(
                        image_train, (-1,) + input_shape)
                )[0]
                image_test_cg[:, r, c, :] = encoder.predict(
                    np.reshape(
                        image_test, (-1,) + input_shape)
                )[0]

    # save data
    dump = {}
    dump['train'] = {}
    dump['test'] = {}

    dump['train']['data'] = image_train_cg
    dump['train']['labels'] = label_train
    dump['test']['data'] = image_test_cg
    dump['test']['labels'] = label_test

    with open("out/cifar_cg.pkl", 'wb') as f:
        pickle.dump(dump, f)
