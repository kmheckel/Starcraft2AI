#this file will handle the training of the "brains" for units in Legion's ai
# it will use a 1D convolutional neural network stacked on an LSTM to analyze a unit and it's 3 closest negihbors
# and forecast it's future health/fitness...

#need to figure out how to define fitness

#need to create the data creation and formatting pipeline...



import tensorflow.keras as keras
from keras.models import Sequential
from keras.layers import Dense, Dropout, Activation, Conv1D, Flatten, MaxPooling1D
from keras.callbacks import TensorBoard
import pickle


# create a tensorboard callback to analyze the models
tensorboard = TensorBoard(log_dir='logs/{}'.format(NAME))

# Load the dataset prepared by our pipeline
X = pickle.load(open("X.pickle", "rb"))
y = pickle.load(open("y.pickle", "rb"))


model = Sequential()

#build conv1D
model.add(Conv1D(64, (3,1), input_shape=))
model.add(Activation("relu"))
#pooling?

model.add(Conv1D(64, (3,1))
model.add(Activation("relu"))

model.add(Flatten())

model.add(Dense(32))
model.add(Activation("relu"))
model.add(Dropout())

model.add(Dense(1))
model.add(Activation("softmax"))


model.compile(loss="categorical_crossentropy", optimizer="adam", metrics=['accuracy'])

model.fit(X, y, batch_size=32, epochs=7, validation_split=.1, callbacks=[tensorboard])

model.save("swarmbrain") # need training instance specific
