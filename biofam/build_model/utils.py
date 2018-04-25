from __future__ import division
from time import sleep

import numpy as np
import scipy as s
import pandas as pd
import numpy.ma as ma
import os
import h5py

from biofam.core.nodes import *


def removeIncompleteSamples(data):
    """ Method to remove samples with missing views

    PARAMETERS
    ----------
    data: list of ndarrays
        list of length M with ndarrays with the observed data of dimensionality (N,Dm)
    """
    print("Removing incomplete samples...")

    M = len(data)
    N = data[0].shape[0]
    samples_to_remove = []
    for n in range(N):
        for m in range(M):
            if pd.isnull(data[m].iloc[n][0]):
                samples_to_remove.append(n)
                break

    print("A total of " + str(len(samples_to_remove)) + " sample(s) have at least a missing view and will be removed")

    data_filt = [None]*M
    samples_to_keep = np.setdiff1d(range(N),samples_to_remove)
    for m in range(M):
        data_filt[m] = data[m].iloc[samples_to_keep]

    return data_filt

def maskData(data, data_opts):
    """ Method to mask values of the data,
    It is mainly used to generate missing values and evaluate imputation

    PARAMETERS
    ----------
    data: list of ndarrays
        list of length M with ndarrays with the observed data of dimensionality (N,Dm)
    data_opts: dictionary
        data_opts['maskAtRandom']
        data_opts['maskNSamples']
    """
    print("Masking data with the following options:")
    print("at random:")
    print(data_opts['maskAtRandom'])
    print("full cases:")
    print(data_opts['maskNSamples'])

    for m in range(len(data)):

        # Mask values at random
        D = data[m].shape[1]
        N = data[m].shape[0]
        p2Mask = data_opts['maskAtRandom'][m]
        if p2Mask != 0:
            idxMask = np.zeros(N*D)
            idxMask[:int(round(N*D*p2Mask))] = 1
            np.random.shuffle(idxMask)
            idxMask = np.reshape(idxMask, [N, D])
            data[m] = data[m].mask(idxMask==1)

        # Mask samples in a complete view
        Nsamples2Mask = data_opts['maskNSamples'][m]
        if Nsamples2Mask != 0:
            idxMask = np.random.choice(N, size=Nsamples2Mask, replace = False)
            # idxMask = np.arange(Nsamples2Mask)
            # print idxMask
            tmp = data[m].copy()
            tmp.ix[idxMask,:] = pd.np.nan
            data[m] = tmp

    return data

def _gaussianise_vec(vec):
    # take ranks and scale to uniform
    vec = s.stats.rankdata(vec, 'dense').astype(float)
    vec /= (vec.max()+1.)

    # transform uniform to gaussian using probit
    vec_norm = np.sqrt(2.) * s.special.erfinv(2.*vec-1.)  # TODO to double check
    # phenotype_norm = np.reshape(phenotype_norm, [len(phenotype_norm), 1])

    return vec_norm

def gaussianise(Y_m, axis=0):
    # double check axis for pandas
    Y_norm = Y_m.apply(_gaussianise_vec, axis)

    return Y_norm

def loadData(data_opts, verbose=True):
    """ Method to load the data

    PARAMETERS
    ----------
    data_opts: dic
    verbose: boolean
    """

    print ("\n")
    print ("#"*18)
    print ("## Loading data ##")
    print ("#"*18)
    print ("\n")
    sleep(1)

    M = len(data_opts['input_files'])

    Y =  [None]*M
    for m in range(M):

        # Read file
        file = data_opts['input_files'][m]
        Y[m] = pd.read_csv(file, delimiter=data_opts["delimiter"], header=data_opts["colnames"], index_col=data_opts["rownames"]).astype(pd.np.float32)

        # Y[m] = pd.read_csv(file, delimiter=data_opts["delimiter"])
        print("Loaded %s with dim (%d, %d)..." % (file, Y[m].shape[0], Y[m].shape[1]))

    # Check that the dimensions match
    if len(set([Y[m].shape[0] for m in range(M)])) != 1:
        if len(set([Y[m].shape[1] for m in range(M)])) == 1:
            print("\nWarning: Columns seem to be the shared axis, transposing the data...")
            for m in range(M): Y[m] = Y[m].T
        else:
            print("\nError: Dimensionalities do not match, aborting. Data should be mapped to one dimension. Please make sure that data files have either rows or columns shared.")
            exit()

    for m in range(M):
        # Removing features with no variance
        var = Y[m].std(axis=0)
        if np.any(var==0.):
            print("Warning: %d features(s) have zero variance, removing them..." % (var==0.).sum())
            Y[m].drop(Y[m].columns[np.where(var==0.)], axis=1, inplace=True)

        # Center the features
        if data_opts['center_features'][m]:
            print("Centering features for view " + str(m) + "...")
            Y[m] = (Y[m] - Y[m].mean(axis=0))

        # Scale the views to unit variance
        if data_opts['scale_views'][m]:
            print("Scaling view " + str(m) + " to unit variance...")
            Y[m] = Y[m] / np.nanstd(Y[m].as_matrix())

        # quantile normalise features
        # if data_opts['gaussianise_features'][m]:
        #     print("Gaussianising features for view " + str(m) + "...")
        #     Y[m] = gaussianise(Y[m])

        # Scale the features to unit variance
        if data_opts['scale_features'][m]:
            print("Scaling features for view " + str(m) + " to unit variance...")
            Y[m] = Y[m] / np.std(Y[m], axis=0, )

        print("\n")

    return Y

def loadDataGroups(data_opts):
    """
    method to load the labels of the samples when there are groups of samples
    """
    if data_opts['sampleGroups'] is None:
        return None
    sample_labels = np.genfromtxt(data_opts['sampleGroups'], dtype='str')
    return sample_labels

def loadDataX(data_opts, transpose = False):
    """ Method to load the data of the samples positions and assigned clusters
    """

    print ("\n")
    print ("#"*18)
    print ("## Loading samples positions data ##")
    print ("#"*18)
    print ("\n")
    sleep(1)

    M = len(data_opts['view_names'])

    if data_opts['X_Files'] is None:

        X = None
        sigma_clust = None

    else:

        if transpose:

            assert M == len(data_opts['X_Files']), "Length of view names and samples positions input files does not match"

            X = [None] * M
            sigma_clust = [None] * M
            for m in range(M):
                file = data_opts['X_Files'][m]
                if file != "None":
                    try:
                        X[m] = np.loadtxt(file, delimiter=',')
                    except:
                        X[m] = np.loadtxt(file, delimiter=' ')

            if data_opts['permute_samples'] == 1:
                for m in range(M):
                    perm = np.random.permutation(D[m])
                    X[m] = X[m][perm, :]

            # load sigma cluster if among arguments
            if data_opts['sigmaClusterFiles'] is not None:
                assert M == len(data_opts['sigmaClusterFiles']), "Length of view names and samples clusters input files does not match"
                for m in range(M):
                    file = data_opts['sigmaClusterFiles'][m]
                    if file != "None":
                        sigma_clust[m] = np.loadtxt(file)

            #if [np.all(X_m == None) for X_m in X] == [True]*M:
            if [X_m is None for X_m in X] == [True] * M: #simplified expression
                X = None

        else:

            assert 1 == len(data_opts['X_Files']), "Length of view names and samples positions input files does not match"

            file = data_opts['X_Files'][0]
            if file != "None":
                try:
                    X = np.loadtxt(file, delimiter=',')
                except:
                    X = np.loadtxt(file, delimiter=' ')

                if data_opts['permute_samples'] == 1:
                    perm = np.random.permutation(N)
                    X = X[perm, :]

                # load sigma cluster if among arguments
                if data_opts['sigmaClusterFiles'] is not None:
                    assert 1 == len(data_opts['sigmaClusterFiles']), "Length of view names and samples clusters input files does not match"
                    sigma_clust = np.loadtxt(data_opts['sigmaClusterFiles'][0])
                else:
                    sigma_clust = None

            else:
                X = None
                sigma_clust = None

    return X, sigma_clust


def corr(A,B):
    """ Method to efficiently compute correlation coefficients between two matrices

    PARAMETERS
    ---------
    A: np array
    B: np array
    """

    # Rowwise mean of input arrays & subtract from input arrays themselves
    A_mA = A - A.mean(1)[:,None]
    B_mB = B - B.mean(1)[:,None]

    # Sum of squares across rows
    ssA = (A_mA**2).sum(1);
    ssB = (B_mB**2).sum(1);

    # Finally get corr coeff
    return np.dot(A_mA, B_mB.T)/np.sqrt(np.dot(ssA[:,None],ssB[None]))

def saveParameters(model, hdf5, view_names=None):
    """ Method to save the parameters of the model in an hdf5 file

    PARAMETERS
    ----------
    model: a BayesNet instance
    hdf5:
    view_names
    """

    # Get nodes from the model
    nodes = model.getNodes()

    # Create groups
    param_grp = hdf5.create_group("parameters")

    # Iterate over nodes
    for node in nodes:

        # Collect node parameters
        parameters = nodes[node].getParameters()

        # Create node subgroup
        node_subgrp = param_grp.create_group(node)

        # Multi-view nodes
        if type(parameters) == list:
            # Loop through the views
            for m in range(len(parameters)):
                if view_names is not None:
                    tmp = view_names[m]
                else:
                    tmp = "%d" % m
                # Create subsubgroup for the view
                view_subgrp = node_subgrp.create_group(tmp)
                # Loop through the parameters of the view
                if parameters[m] is not None:
                    # Variational nodes
                    if type(parameters[m]) == dict:
                        for param_name in parameters[m].keys():
                            if parameters[m][param_name] is not None:
                                view_subgrp.create_dataset(param_name, data=parameters[m][param_name].T)
                    # Non-variational nodes (no distributions)
                    elif type(parameters[m]) == np.ndarray:
                           view_subgrp.create_dataset("value", data=parameters[m].T)

        # Single-view nodes
        else:
            for param_name in parameters.keys():
                node_subgrp.create_dataset("%s" % (param_name), data=parameters[param_name].T)
    pass

def saveExpectations(model, hdf5, view_names=None, only_first_moments=True):
    """ Method to save the expectations of the model in an hdf5 file

    PARAMETERS
    ----------
    model: a BayesNet instance
    hdf5:
    view_names
    only_first_moments
    """
    # Get nodes from the model
    nodes = model.getNodes()

    exp_grp = hdf5.create_group("expectations")

    # Iterate over nodes
    for node in nodes:

        # Collect node expectations
        expectations = nodes[node].getExpectations()

        # Create subgroup for the node
        node_subgrp = exp_grp.create_group(node)

        # Multi-view nodes
        if type(expectations) == list:

            # Iterate over views
            for m in range(len(expectations)):
                if view_names is not None:
                    tmp = view_names[m]
                else:
                    tmp = "%d" % m

                # Create subsubgroup for the view
                view_subgrp = node_subgrp.create_group(tmp)

                # Loop through the expectations
                if only_first_moments:
                    if node == "SW":
                        expectations[m] = {'E':expectations[m]["E"], 'ES':expectations[m]["EB"], 'EW':expectations[m]["EN"]}
                    else:
                        expectations[m] = {'E':expectations[m]["E"]}

                if expectations[m] is not None:

                    # is the node a Sigma node ? since we cannot transpose its expectation (list of matrices, not tensors)
                    SigmaNode = node == "SigmaAlphaW" and nodes[node].getNodes()[m].__class__.__name__ != "AlphaW_Node_mk"

                    for exp_name in expectations[m].keys():
                        if type(expectations[m][exp_name]) == ma.core.MaskedArray:
                            tmp = ma.filled(expectations[m][exp_name], fill_value=np.nan)
                            if SigmaNode:
                                view_subgrp.create_dataset(exp_name, data=tmp)
                            else:
                                view_subgrp.create_dataset(exp_name, data=tmp.T)

                        else:
                            if SigmaNode:
                                view_subgrp.create_dataset(exp_name, data=expectations[m][exp_name])
                            else:
                                view_subgrp.create_dataset(exp_name, data=expectations[m][exp_name].T)


        # Single-view nodes
        else:
            if node == "SZ":
                expectations = {'E':expectations["E"], 'ES':expectations["EB"], 'EZ':expectations["EN"]}
            if only_first_moments: expectations = {'E':expectations["E"]}
            for exp_name in expectations.keys():

                # is the node a Sigma node ? since we cannot transpose its expectation (list of matrices, not tensors)
                if node == "SigmaZ":
                    node_subgrp.create_dataset("%s" % (exp_name), data=expectations[exp_name])
                else:
                    node_subgrp.create_dataset("%s" % (exp_name), data=expectations[exp_name].T)

def saveTrainingStats(model, hdf5):
    """ Method to save the training statistics in an hdf5 file

    PARAMETERS
    ----------
    model: a BayesNet instance
    hdf5:
    """
    stats = model.getTrainingStats()
    stats_grp = hdf5.create_group("training_stats")
    stats_grp.create_dataset("activeK", data=stats["activeK"])
    stats_grp.create_dataset("elbo", data=stats["elbo"])
    stats_grp.create_dataset("elbo_terms", data=stats["elbo_terms"].T)
    stats_grp['elbo_terms'].attrs['colnames'] = [a.encode('utf8') for a in stats["elbo_terms"].columns.values]

def saveTrainingOpts(opts, hdf5):
    """ Method to save the training options in an hdf5 file

    PARAMETERS
    ----------
    opts:
    hdf5:
    """
    # Remove dictionaries from the options
    for k,v in opts.copy().items():
        if type(v)==dict:
            for k1,v1 in v.items():
                opts[str(k)+"_"+str(k1)] = v1
            opts.pop(k)

    # Create HDF5 data set
    if 'schedule' in opts.keys():
        del opts['schedule']
    # For more info see the issue with UTF-8 strings in Python3 and h5py: https://github.com/h5py/h5py/issues/289
    hdf5.create_dataset("training_opts".encode('utf8'), data=np.array(list(opts.values()), dtype=np.float))
    hdf5['training_opts'].attrs['names'] = np.asarray(list(opts.keys())).astype('S')

def saveModelOpts(opts, hdf5):
    """ Method to save the model options in an hdf5 file

    PARAMETERS
    ----------
    opts:
    hdf5:
    """
    # opts_interest = ["learnIntercept", "schedule", "likelihood"]
    opts_interest = ["learnIntercept", "likelihood", "transpose_noise", "transpose_sparsity"]
    opts = dict((k, opts[k]) for k in opts_interest)
    grp = hdf5.create_group('model_opts')
    for k, v in opts.items():
        grp.create_dataset(k, data=np.asarray(v).astype('S'))
    grp[k].attrs['names'] = np.asarray(list(opts.keys())).astype('S')

def saveTrainingData(model, hdf5, view_names=None, sample_names=None, feature_names=None, shared_features=False):
    """ Method to save the training data in an hdf5 file

    PARAMETERS
    ----------
    model: a BayesNet instance
    hdf5:
    view_names
    sample_names
    feature_names
    """
    data = model.getTrainingData()
    data_grp = hdf5.create_group("data")
    if shared_features:
        # Save features (shared between views)
        if feature_names is not None:
            hdf5.create_dataset("features", data=[str(f).encode('utf8') for f in feature_names])
        # Save samples (per view)
        sampledata_grp = hdf5.create_group("samples")
        for m in range(len(data)):
            view = view_names[m] if view_names is not None else str(m)
            data_grp.create_dataset(view, data=data[m].data.T)
            if sample_names is not None:
                sampledata_grp.create_dataset(view, data=[str(s).encode('utf8') for s in sample_names[m]])
    else:
        # Save samples (shared between views)
        if sample_names is not None:
            hdf5.create_dataset("samples", data=[str(s).encode('utf8') for s in sample_names])
        # Save features (per view)
        featuredata_grp = hdf5.create_group("features")
        for m in range(len(data)):
            view = view_names[m] if view_names is not None else str(m)
            data_grp.create_dataset(view, data=data[m].data.T)
            if feature_names is not None:
                featuredata_grp.create_dataset(view, data=[str(f).encode('utf8') for f in feature_names[m]])

def saveDataTxt(model, outDir, view_names=None, sample_names=None, feature_names=None, shared_features=False):
    """ Method to save the training data in text files

    PARAMETERS
    ----------
    model: a BayesNet instance
    outDir
    view_names
    sample_names
    feature_names
    """
    data = model.getTrainingData()
    for m in range(len(data)):
        view = view_names[m] if view_names is not None else 'view_' + str(m)
        file_name = outDir + '/' + view
        to_save = pd.DataFrame(data[m].data)
        if feature_names is not None: #shared features or not -> to distinguish
            if shared_features:
                to_save.columns = feature_names
            else:
                to_save.columns = feature_names[m]
        if sample_names is not None:
            if shared_features:
                to_save.index = sample_names[m]
            else:
                to_save.index = sample_names
        to_save.to_csv(file_name)

def saveDataXTxt(model, outDir, transpose, view_names=None, sample_names=None):
    """ Method to save the X_Files data in text files (X_Files : positions of the samples)

    PARAMETERS
    ----------
    model: a BayesNet instance
    outDir
    view_names
    sample_names
    """
    if transpose:
        dataX = [SigmaAlphaW_m["X"] for SigmaAlphaW_m in model.getNodes()["SigmaAlphaW"].getParameters()]
        for m in range(len(dataX)):
            view = view_names[m] if view_names is not None else 'view_' + str(m)
            file_name = outDir + '/' + "X_file_" + view
            to_save = pd.DataFrame(dataX[m])
            #to_save.columns = ["x1", "x2"]
            if sample_names is not None:
                to_save.index = sample_names
            to_save.to_csv(file_name, index=False, header=False)
    else:
        dataX = model.getNodes()["SigmaZ"].getParameters()["X"]
        file_name = outDir + '/' + "X_file"
        to_save = pd.DataFrame(dataX)
        #to_save.columns = ["x1","x2"]
        if sample_names is not None:
            to_save.index = sample_names
        to_save.to_csv(file_name, index=False, header=False)


def overwriteExpectations(net):
    """
    methods to overwrite the expectations of the Q distributions with sampled
    values in cases where we don't train the network but do only simulations

    This enables saving the values more easily
    """
    for node in net.nodes.keys():
        if isinstance(net.nodes[node], Multiview_Node):
            overwriteExpectationsMV(net.nodes[node])
        if isinstance(net.nodes[node], Unobserved_Variational_Node):
            net.nodes[node].Q.expectations["E"] = net.nodes[node].samp
        if isinstance(net.nodes[node], Constant_Variational_Node):
            net.nodes[node].value = net.nodes[node].samp
        if node=='Sigma':
            net.nodes[node].ix = net.nodes[node].samp

def overwriteExpectationsMV(MV):
    """
    specific overwrite functions for multiview nodes
    """
    for node in MV.nodes:
        if isinstance(node, Unobserved_Variational_Node):
            node.Q.expectations["E"] = node.samp
        if isinstance(node, Constant_Variational_Node):
            node.value = node.samp
        if isinstance(node, Y_Node):
            node.value = node.samp
            node.mask()
        if isinstance(node, PseudoY):
            node.value = node.samp
            node.mask()


def saveTrainedModel(model, outfile, train_opts, model_opts, view_names=None, sample_names=None, feature_names=None, shared_features=False):
    """ Method to save the model in an hdf5 file

    PARAMETERS
    ----------
    """
    assert model.trained, "Model is not trained yet"

    if view_names is not None:
        assert len(np.unique(view_names)) == len(view_names), 'View names must be unique'

        # For some reason h5py orders the datasets alphabetically, so we have to modify the likelihood accordingly
        idx = sorted(range(len(view_names)), key=lambda k: view_names[k])
        tmp = [model_opts["likelihood"][idx[m]] for m in range(len(model_opts["likelihood"]))]
        model_opts["likelihood"] = tmp

    if shared_features:
        if feature_names is not None:
            assert len(np.unique(feature_names)) == len(feature_names), 'Feature names must be unique'
    else:
        if sample_names is not None:
            assert len(np.unique(sample_names)) == len(sample_names), 'Sample names must be unique'

    hdf5 = h5py.File(outfile,'w')
    saveExpectations(model,hdf5,view_names)
    saveParameters(model,hdf5, view_names)
    saveModelOpts(model_opts, hdf5)
    saveTrainingData(model, hdf5, view_names, sample_names, feature_names, shared_features)
    saveTrainingStats(model, hdf5)
    saveTrainingOpts(train_opts, hdf5)

    hdf5.close()

def saveSimulatedModel(model, outfile, train_opts, model_opts, view_names=None, sample_names=None, feature_names=None,  shared_features=False):
    """ Method to save the model in an hdf5 file

    PARAMETERS
    ----------
    """
    assert model.simulated, "Model is not simulated yet"

    if view_names is not None:
        assert len(np.unique(view_names)) == len(view_names), 'View names must be unique'

        # For some reason h5py orders the datasets alphabetically, so we have to modify the likelihood accordingly
        idx = sorted(range(len(view_names)), key=lambda k: view_names[k])
        tmp = [model_opts["likelihood"][idx[m]] for m in range(len(model_opts["likelihood"]))]
        model_opts["likelihood"] = tmp

    if shared_features:
        if feature_names is not None:
            assert len(np.unique(feature_names)) == len(feature_names), 'Feature names must be unique'
    else:
        if sample_names is not None:
            assert len(np.unique(sample_names)) == len(sample_names), 'Sample names must be unique'

    overwriteExpectations(model)
    if 'outDir' in model_opts:
        saveDataTxt(model, model_opts['outDir'], view_names=view_names, sample_names=sample_names, feature_names=feature_names, shared_features=shared_features)

        if model_opts['sample_X']:
            saveDataXTxt(model, model_opts['outDir'], model_opts["transpose_sparsity"], view_names=view_names) #, sample_names=sample_names)

    hdf5 = h5py.File(outfile,'w')
    saveExpectations(model,hdf5,view_names)
    saveParameters(model,hdf5,view_names)
    saveModelOpts(model_opts,hdf5)
    saveTrainingData(model, hdf5, view_names, sample_names, feature_names, shared_features)

    hdf5.close()
