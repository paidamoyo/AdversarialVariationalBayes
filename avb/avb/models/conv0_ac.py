import tensorflow as tf
from tensorflow.contrib import slim
from avb.ops import *

def encoder(x, config, eps=None, is_training=True):
    output_size = config['output_size']
    c_dim = config['c_dim']
    df_dim = config['df_dim']
    z_dist = config['z_dist']
    z_dim = config['z_dim']
    eps_dim = config['eps_dim']
    eps_nbasis = config['eps_nbasis']

    # Center x at 0
    x = 2*x - 1

    # Noise
    if eps is None:
        batch_size = tf.shape(x)[0]
        eps = tf.random_normal(tf.stack([eps_nbasis, batch_size, eps_dim]))

    # Coefficients
    n_down = max(min(int(math.log(output_size, 2)) - 2, 4), 0)
    filter_strides = [(1, 1)] * (4 - n_down) + [(2, 2)] * n_down

    bn_kwargs = {
        'scale': True, 'center':True, 'is_training': is_training, 'updates_collections': None
    }

    conv2d_argscope = slim.arg_scope([slim.conv2d],
            activation_fn=tf.nn.elu, kernel_size=(5, 5),
            normalizer_fn=None, normalizer_params=bn_kwargs)

    with conv2d_argscope:
        net = slim.conv2d(x, 1*df_dim, stride=filter_strides[0], scope="conv_0")
        net = slim.conv2d(net, 2*df_dim, stride=filter_strides[1], scope="conv_1")
        net = slim.conv2d(net, 4*df_dim, stride=filter_strides[2], scope="conv_2")
        net = slim.conv2d(net, 8*df_dim, stride=filter_strides[3], normalizer_fn=None, scope="conv_3")

    net = flatten_spatial(net)

    z0 = slim.fully_connected(net, z_dim, activation_fn=None, scope='z0',
        weights_initializer=tf.truncated_normal_initializer(stddev=1e-5))

    a_vec = []
    for i in range(eps_nbasis):
        a = slim.fully_connected(net, z_dim, activation_fn=None, scope='a_%d' % i)
        a = tf.nn.elu(a - 5.) + 1.
        a_vec.append(a)

    # Sample and Moments
    if eps is None:
        batch_size = tf.shape(x)[0]
        eps = tf.random_normal(tf.stack([eps_nbasis, batch_size, eps_dim]))

    v_vec = []
    for i in range(eps_nbasis):
        with tf.variable_scope("eps_%d" % i):
            fc_argscope = slim.arg_scope([slim.fully_connected],
                            activation_fn=tf.nn.elu)
            with fc_argscope:
                net = slim.fully_connected(eps[i], 128, scope='fc_0')
                net = slim.fully_connected(net, 128, scope='fc_1')
                net = slim.fully_connected(net, 128, scope='fc_2')
            v = slim.fully_connected(net, z_dim, activation_fn=None, scope='v')

            v_vec.append(v)

    # Sample and Moments
    z = z0
    Ez = z0
    Varz = 0.

    for a, v in zip(a_vec, v_vec):
        z += a*v
        Ev, Varv = tf.nn.moments(v, [0])
        Ez += a*Ev
        Varz += a*a*Varv

    # if z_dist == "uniform":
    #     z = tf.nn.sigmoid(z)

    return z, Ez, Varz
