# ---------------------------------------------------------#
#   astroNN.models.cnn: Contain CNN Model
# ---------------------------------------------------------#
import os

import numpy as np
from keras import regularizers
from keras.backend import clear_session
from keras.callbacks import ReduceLROnPlateau, CSVLogger
from keras.layers import MaxPooling1D, Conv1D, Dense, Dropout, Flatten
from keras.models import Model, Input
from keras.optimizers import Adam

from astroNN.models.models_shared import ModelStandard
from astroNN.models.models_tools import threadsafe_generator


class CNN(ModelStandard):
    """
    NAME:
        CNN
    PURPOSE:
        To create Convolutional Neural Network model
    HISTORY:
        2017-Dec-21 - Written - Henry Leung (University of Toronto)
    """

    def __init__(self):
        """
        NAME:
            model
        PURPOSE:
            To create Convolutional Neural Network model
        INPUT:
        OUTPUT:
        HISTORY:
            2017-Dec-21 - Written - Henry Leung (University of Toronto)
        """
        super(CNN, self).__init__()

        self.name = 'Conventional Convolutional Neural Network'
        self._model_type = 'CNN'
        self._implementation_version = '1.0'
        self.batch_size = 64
        self.initializer = 'he_normal'
        self.activation = 'relu'
        self.num_filters = [2, 4]
        self.filter_length = 8
        self.pool_length = 4
        self.num_hidden = [196, 96]
        self.max_epochs = 250
        self.lr = 0.005
        self.reduce_lr_epsilon = 0.00005
        self.reduce_lr_min = 1e-8
        self.reduce_lr_patience = 10
        self.data_normalization = True
        self.target = 'all'
        self.l2 = 1e-7

    def model(self):
        input_tensor = Input(shape=self.input_shape)
        cnn_layer_1 = Conv1D(kernel_initializer=self.initializer, activation=self.activation, padding="same",
                             filters=self.num_filters[0],
                             kernel_size=self.filter_length, kernel_regularizer=regularizers.l2(self.l2))(input_tensor)
        cnn_layer_2 = Conv1D(kernel_initializer=self.initializer, activation=self.activation, padding="same",
                             filters=self.num_filters[0],
                             kernel_size=self.filter_length, kernel_regularizer=regularizers.l2(self.l2))(cnn_layer_1)
        maxpool_1 = MaxPooling1D(pool_size=self.pool_length)(cnn_layer_2)
        flattener = Flatten()(maxpool_1)
        dropout_1 = Dropout(0.1)(flattener)
        layer_3 = Dense(units=self.num_hidden[1], kernel_regularizer=regularizers.l2(self.l2),
                        kernel_initializer=self.initializer,
                        activation=self.activation)(dropout_1)
        dropout_2 = Dropout(0.05)(layer_3)
        layer_4 = Dense(units=self.num_hidden[1], kernel_regularizer=regularizers.l2(self.l2),
                        kernel_initializer=self.initializer,
                        activation=self.activation)(dropout_2)
        linear_output = Dense(units=self.output_shape[0], activation="linear", name='linear_output')(layer_4)

        model = Model(inputs=input_tensor, outputs=linear_output)

        return model

    def compile(self):
        if self.optimizer is None or self.optimizer == 'adam':
            self.optimizer = Adam(lr=self.lr, beta_1=self.beta_1, beta_2=self.beta_2, epsilon=self.optimizer_epsilon,
                                  decay=0.0)

        self.keras_model = self.model()
        if self.task == 'regression':
            self.keras_model.compile(loss=self.mean_squared_error, optimizer=self.optimizer)
        elif self.task == 'classification':
            self.keras_model.compile(loss=self.categorical_cross_entropy, optimizer=self.optimizer)
        return None

    def train(self, x_data, y_data):
        x_data, y_data = super().train(x_data, y_data)

        csv_logger = CSVLogger(self.fullfilepath + 'log.csv', append=True, separator=',')

        reduce_lr = ReduceLROnPlateau(monitor='loss', factor=0.5, epsilon=self.reduce_lr_epsilon,
                                      patience=self.reduce_lr_patience, min_lr=self.reduce_lr_min, mode='min',
                                      verbose=2)
        self.compile()
        self.plot_model()

        training_generator = DataGenerator(x_data.shape[1], self.batch_size).generate(x_data, y_data)

        self.keras_model.fit_generator(generator=training_generator, steps_per_epoch=x_data.shape[0] // self.batch_size,
                                       epochs=self.max_epochs, max_queue_size=20, verbose=2, workers=os.cpu_count(),
                                       callbacks=[reduce_lr, csv_logger])

        astronn_model = 'model_weights.h5'
        self.keras_model.save_weights(self.fullfilepath + astronn_model)
        print(astronn_model + ' saved to {}'.format(self.fullfilepath + astronn_model))

        clear_session()

        return None

    def test(self, x):
        x = super().test(x)
        predictions = self.keras_model.predict(x)
        data = np.load(self.fullfilepath + '/meanstd.npy')
        predictions *= data[1]
        predictions += data[0]

        return predictions


class DataGenerator(object):
    """
    NAME:
        DataGenerator
    PURPOSE:
        To generate data for Keras
    INPUT:
    OUTPUT:
    HISTORY:
        2017-Dec-02 - Written - Henry Leung (University of Toronto)
    """

    def __init__(self, dim, batch_size, shuffle=True):
        'Initialization'
        self.dim = dim
        self.batch_size = batch_size
        self.shuffle = shuffle

    def __get_exploration_order(self, list_IDs):
        'Generates order of exploration'
        # Find exploration order
        indexes = np.arange(len(list_IDs))
        if self.shuffle is True:
            np.random.shuffle(indexes)

        return indexes

    def __data_generation(self, spectra, labels, list_IDs_temp):
        'Generates data of batch_size samples'
        # X : (n_samples, v_size, n_channels)
        # Initialization
        X = np.empty((self.batch_size, self.dim, 1))
        y = np.empty((self.batch_size, labels.shape[1]))

        # Generate data
        X[:, :, 0] = spectra[list_IDs_temp]
        y[:] = labels[list_IDs_temp]

        return X, y

    @threadsafe_generator
    def generate(self, input, labels):
        'Generates batches of samples'
        # Infinite loop
        list_IDs = range(input.shape[0])
        while 1:
            # Generate order of exploration of dataset
            indexes = self.__get_exploration_order(list_IDs)

            # Generate batches
            imax = int(len(indexes) / self.batch_size)
            for i in range(imax):
                # Find list of IDs
                list_IDs_temp = indexes[i * self.batch_size:(i + 1) * self.batch_size]

                # Generate data
                X, y = self.__data_generation(input, labels, list_IDs_temp)

                yield X, y
