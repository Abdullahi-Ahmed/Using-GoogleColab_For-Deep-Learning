import pandas as pd
import numpy as np
import seaborn as sns

import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

import io
df = pd.read_csv("/content/loan_data (1).csv")


count_class_0, count_class_1 = df['TARGET'].value_counts()
df_0 = df[df['TARGET'] == 0]
df_1 = df[df['TARGET'] == 1]
df_1_over = df_1.sample(count_class_0, replace=True)
df_test_over = pd.concat([df_0, df_1_over], axis=0)
print('Random over-sampling:')
print(df_test_over['TARGET'].value_counts())

def rmissingvaluecol(dff, threshold):
    l = []
    l = list(dff.drop(dff.loc[:,list((100*(dff.isnull().sum()/len(dff.index)) >= threshold))].columns, 1).columns.values)
    print("# Columns having more than %s percent missing values: "%threshold, (dff.shape[1] - len(l)))
    print("Columns:\n", list(set(list((dff.columns.values))) - set(l)))
    return l


rmissingvaluecol(df,50)

l = rmissingvaluecol(df, 50)
newdf = df[l]

newdf['NAME_TYPE_SUITE'].fillna(newdf['NAME_TYPE_SUITE'].mode()[0], inplace=True)
newdf['OCCUPATION_TYPE'].fillna(newdf['OCCUPATION_TYPE'].mode()[0], inplace=True)
newdf['EMERGENCYSTATE_MODE'].fillna(newdf['EMERGENCYSTATE_MODE'].mode()[0], inplace=True)


df_missing_values=[]
for col in newdf.columns:
    if newdf[col].isnull().sum() !=0:
         df_missing_values.append(col)
print(df_missing_values)

for col in newdf.columns:
    if col in (df_missing_values):
        newdf[col].replace(np.nan, newdf[col].mean(),inplace=True)

len(newdf.columns[newdf.isnull().sum(axis = 0)> 0])

# Create correlation matrix
corr_matrix = newdf.corr()

# Select upper triangle of correlation matrix
upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(np.bool))

# Find index of feature columns with correlation greater than 0.90
highly_Correlated = [column for column in upper.columns if any(abs(upper[column]) > 0.90)]

highly_Correlated


#droping unneccesary columns like the ones that have high correlation
cols_drop = ['AMT_GOODS_PRICE',
 'FLAG_EMP_PHONE',
 'REGION_RATING_CLIENT_W_CITY',
 'YEARS_BEGINEXPLUATATION_MODE',
 'FLOORSMAX_MODE',
 'YEARS_BEGINEXPLUATATION_MEDI',
 'FLOORSMAX_MEDI',
 'OBS_60_CNT_SOCIAL_CIRCLE']


for data in [newdf]:
    data.drop(columns = cols_drop,inplace=True)

obj_df = newdf.select_dtypes(include=['object'])

from sklearn import preprocessing
newdf = newdf.apply(preprocessing.LabelEncoder().fit_transform)

newdf.dtypes.value_counts()
X = newdf.drop(['TARGET'], axis=1)
y = newdf['TARGET']

from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(X,y, test_size = 0.2, random_state = 42)

from keras.layers import Input, Dense
from keras.models import Model, Sequential
from keras import regularizers
from keras import optimizers
import tensorflow as tf

from sklearn.base import BaseEstimator


class NaivePredictor(BaseEstimator):
    """ Naive predictor is a benchmark
        model that will always predict that a loan
        will always get repaid.
    """

    def fit(self, X, y):
        """Do nothing"""
        pass

    def predict(self, X):
        """ Always predict 0 for loan repayment."""
        return np.zeros(X.shape[0])

    def predict_proba(self, X):
        """ Return probability 100% for loan repayment."""
        prob = np.zeros((X.shape[0], 2))

        # predict 100% loan repayment
        prob[:, 0] = 1

        return prob


def auc_roc(y_true, y_pred):
    # any tensorflow metric
    #     value, update_op = tf.contrib.metrics.streaming_auc(y_pred, y_true)
    value, update_op = tf.metrics.auc(y_pred, y_true)

    # find all variables created for this metric
    metric_vars = [i for i in tf.local_variables() if 'auc_roc' in i.name.split('/')[1]]

    # Add metric variables to GLOBAL_VARIABLES collection.
    # They will be initialized for new session.
    for v in metric_vars:
        tf.add_to_collection(tf.GraphKeys.GLOBAL_VARIABLES, v)

    # force to update metric values
    with tf.control_dependencies([update_op]):
        value = tf.identity(value)
        return value


class NeuralNetwork(BaseEstimator):
    """ Two layer neural network.
    """

    def __init__(self, input_shape=None, epochs=15, batch_size=250, optimizer='adagrad', init='normal'):

        self.optimizer = optimizer
        self.init = init
        self.batch_size = batch_size
        self.epochs = epochs
        self.input_shape = input_shape

        self.model_ = Sequential()
        self.model_.add(Dense(300, input_dim=input_shape, kernel_initializer=self.init, activation='relu'))
        self.model_.add(Dense(1, kernel_initializer=self.init, activation='sigmoid'))
        self.model_.compile(loss='binary_crossentropy', optimizer=self.optimizer, metrics=[auc_roc])

    def fit(self, X, y, valid_set=None):
        """Fit model"""

        if valid_set is None:
            return self.model_.fit(X, y, epochs=self.epochs, verbose=0, validation_split=0.1,
                                   batch_size=self.batch_size)
        else:
            return self.model_.fit(X, y, epochs=self.epochs, verbose=0, validation_data=valid_set,
                                   batch_size=self.batch_size)

    def predict(self, X, y=None):
        """ Always predict 0 for loan repayment."""
        probs = np.zeros((X.shape[0], 2))
        probs[:, 1] = self.model_.predict(X).flatten()
        probs[:, 0] = 1 - probs[:, 1]

        return np.argmax(probs, axis=1)

    def score(self, X, y=None):
        # counts number of values bigger than mean
        return (sum(self.predict(X)))

    def predict_proba(self, X):
        """ Return probability ."""
        probs = np.zeros((X.shape[0], 2))
        probs[:, 1] = self.model_.predict(X).flatten()
        probs[:, 0] = 1 - probs[:, 1]

        return probs

from sklearn.metrics import roc_auc_score
from sklearn.metrics import roc_curve


#define bench mark model and train it
bench = NaivePredictor()
bench.fit(X_train, y_train )

# predict probabilities
# keep probabilities for the positive outcome only
probs_bench = bench.predict_proba(X_test)[:,1]

# calculate AUC
auc_bench = roc_auc_score(y_test, probs_bench)
print('Bench AUC: {:.4f}'.format(auc_bench))

# calculate roc curve
fpr_bench, tpr_bench, thresholds_bench  = roc_curve(y_test, probs_bench)

# plot the roc curve for the model

plt.plot(fpr_bench, tpr_bench,linestyle='--',label='Naive')

plt.xlabel('False positive rate')
plt.ylabel('True positive rate')

# show the plot
plt.legend()
plt.show()