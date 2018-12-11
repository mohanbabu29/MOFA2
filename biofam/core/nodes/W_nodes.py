from __future__ import division
import numpy.ma as ma
import numpy as np
import scipy as s
import math

from biofam.core.utils import *
from biofam.core import gpu_utils


# Import manually defined functions
from .variational_nodes import BernoulliGaussian_Unobserved_Variational_Node
from .variational_nodes import UnivariateGaussian_Unobserved_Variational_Node
from .variational_nodes import UnivariateGaussian_Unobserved_Variational_Node_with_MultivariateGaussian_Prior

class W_Node(UnivariateGaussian_Unobserved_Variational_Node):
    def __init__(self, dim, pmean, pvar, qmean, qvar, qE=None, qE2=None, idx_covariates=None):
        super().__init__(dim=dim, pmean=pmean, pvar=pvar, qmean=qmean, qvar=qvar, qE=qE, qE2=qE2)
        print("Not functional")
        exit()
        # Define indices for covariates
        if idx_covariates is not None:
            self.covariates[idx_covariates] = True

    def precompute(self, options):
        # Precompute terms to speed up computation
        self.dim[0] = self.dim[0]
        self.K = self.dim[1]
        self.covariates = np.zeros(self.dim[1], dtype=bool)
        self.factors_axis = 1

        gpu_utils.gpu_mode = options['gpu_mode']

    def getLvIndex(self):
        # Method to return the index of the latent variables (without covariates)
        latent_variables = np.array(range(self.dim[1]))
        if any(self.covariates):
            # latent_variables = np.delete(latent_variables, latent_variables[self.covariates])
            latent_variables = latent_variables[~self.covariates]
        return latent_variables

    def removeFactors(self, idx):
        super().removeFactors(idx, axis=1)

    def updateParameters(self, ix=None, ro=None):
        """
        Public function to update the nodes parameters
        Optional arguments for stochastic updates are:
            - ix: list of indices of the minibatch
            - ro: step size of the natural gradient ascent
        """
        #-----------------------------------------------------------------------
        # get Expectations which are necessarry for the update
        #-----------------------------------------------------------------------
        Y = self.markov_blanket["Y"].getExpectation()
        Z = self.markov_blanket["Z"].get_mini_batch()
        tau = self.markov_blanket["Tau"].get_mini_batch()
        N = self.markov_blanket["Y"].dim[0]

        # Collect parameters from the prior or expectations from the markov blanket
        if "MuW" in self.markov_blanket:
            Mu = self.markov_blanket['MuW'].getExpectation()
        else:
            Mu = self.P.getParameters()["mean"]

        if "AlphaW" in self.markov_blanket:
            Alpha = self.markov_blanket['AlphaW'].getExpectation(expand=True)
        else:
            Alpha = 1./self.P.params['var']

        # Collect parameters from the Q distributions of this node
        Q = self.Q.getParameters()
        Qmean, Qvar = Q['mean'], Q['var']

        #-----------------------------------------------------------------------
        # Masking
        #-----------------------------------------------------------------------
        mask = ma.getmask(Y)
        Y = Y.data
        tau[mask] = 0.
        Y[mask] = 0.

        #-----------------------------------------------------------------------
        # compute stochastic "anti-bias" coefficient
        #-----------------------------------------------------------------------
        coeff = float(N) / float(Y.shape[0])

        #-----------------------------------------------------------------------
        # make sure ro is not None
        #-----------------------------------------------------------------------
        if ro is None:
            ro = 1.

        #-----------------------------------------------------------------------
        # compute the update
        #-----------------------------------------------------------------------
        self._updateParameters(Y, Z, tau, Mu, Alpha, Qmean, Qvar, coeff, ro)

    def _updateParameters(self, Y, Z, tau, Mu, Alpha, Qmean, Qvar, coeff, ro):

        latent_variables = self.getLvIndex() # excluding covariates from the list of latent variables

        for k in latent_variables:
            foo = coeff * np.dot(Z["E2"][:,k],tau)

            bar_tmp1 = gpu_utils.array(Z["E"][:,k])

            bar_tmp2 = - gpu_utils.dot(gpu_utils.array(Z["E"][:,s.arange(self.dim[1])!=k]),
                               gpu_utils.array(Qmean[:,s.arange(self.dim[1])!=k].T))
            bar_tmp2 += gpu_utils.array(Y)
            bar_tmp2 *= gpu_utils.array(tau)

            bar = coeff * gpu_utils.asnumpy(gpu_utils.dot(bar_tmp1, bar_tmp2))

            # stochastic update of W
            Qvar[:,k] *= (1 - ro)
            Qvar[:,k] += ro/(Alpha[:,k]+foo)

            # NOTE Do not use "Qvar" in the update like we used to because this
            # does not hold for stochastic because of the ro weighting
            Qmean[:,k] *= (1 - ro)
            Qmean[:,k] += ro * (1/(Alpha[:,k]+foo)) * (bar + Alpha[:,k]*Mu[:,k])

    def calculateELBO(self):

        # Collect parameters and expectations of current node
        Qpar,Qexp = self.Q.getParameters(), self.Q.getExpectations()
        Qmean, Qvar = Qpar['mean'], Qpar['var']
        QE, QE2 = Qexp['E'],Qexp['E2']

        if "MuW" in self.markov_blanket:
            PE, PE2 = self.markov_blanket['MuW'].getExpectations()['E'], self.markov_blanket['MuW'].getExpectations()['E2']
        else:
            PE, PE2 = self.P.getParameters()["mean"], s.zeros((self.dim[0],self.dim[1]))

        if 'AlphaW' in self.markov_blanket:
            Alpha = self.markov_blanket["AlphaW"].getExpectations(expand=True)
        else:
            Alpha = dict()
            Alpha['E'] = 1./self.P.params['var']
            Alpha['lnE'] = s.log(1./self.P.params['var'])

        # This ELBO term contains only cross entropy between Q and P,and entropy of Q. So the covariates should not intervene at all
        latent_variables = self.getLvIndex()
        Alpha["E"], Alpha["lnE"] = Alpha["E"][:, latent_variables], Alpha["lnE"][:, latent_variables]
        Qmean, Qvar = Qmean[:, latent_variables], Qvar[:, latent_variables]
        PE, PE2 = PE[:, latent_variables], PE2[:, latent_variables]
        QE, QE2 = QE[:, latent_variables], QE2[:, latent_variables]

        # compute term from the exponential in the Gaussian
        tmp1 = 0.5 * QE2 - PE * QE + 0.5 * PE2
        tmp1 = -(tmp1 * Alpha['E']).sum()

        # compute term from the precision factor in front of the Gaussian
        tmp2 = 0.5 * Alpha["lnE"].sum()

        lb_p = tmp1 + tmp2
        # lb_q = -(s.log(Qvar).sum() + self.dim[0]*self.dim[1])/2. # I THINK THIS IS WRONG BECAUSE SELF.DIM[1] ICNLUDES COVARIATES
        lb_q = -(s.log(Qvar).sum() + self.dim[0] * len(latent_variables)) / 2.

        return lb_p-lb_q


class SW_Node(BernoulliGaussian_Unobserved_Variational_Node):
    def __init__(self, dim, pmean_S0, pmean_S1, pvar_S0, pvar_S1, ptheta, qmean_S0, qmean_S1, qvar_S0, qvar_S1, qtheta, qEW_S0=None, qEW_S1=None, qES=None):
        super().__init__(dim, pmean_S0, pmean_S1, pvar_S0, pvar_S1, ptheta, qmean_S0, qmean_S1, qvar_S0, qvar_S1, qtheta, qEW_S0, qEW_S1, qES)

    def precompute(self, options):
        self.factors_axis = 1
        gpu_utils.gpu_mode = options['gpu_mode']
    # @profile
    def updateParameters(self, ix=None, ro=1.):

        # Collect expectations from other nodes
        Y = self.markov_blanket["Y"].get_mini_batch()
        Z = self.markov_blanket["Z"].get_mini_batch()
        tau = self.markov_blanket["Tau"].get_mini_batch()
        mask = self.markov_blanket["Y"].getMask()

        if "AlphaW" in self.markov_blanket:
            Alpha = self.markov_blanket["AlphaW"].getExpectation(expand=True)
        else:
            Alpha = 1./self.P.params['var_B1']

        thetatmp = self.markov_blanket["ThetaW"].getExpectations(expand=True)
        theta_lnE, theta_lnEInv  = thetatmp['lnE'], thetatmp['lnEInv']

        # This node
        SW = self.Q.getExpectations()["E"]
        Q = self.Q.getParameters()
        Qmean_S1, Qvar_S1, Qvar_S0 = Q['mean_B1'], Q['var_B1'],  Q['var_B0']
        Qtheta = Q['theta']

        # Compute stochastic "anti-bias" coefficient
        N = self.markov_blanket["Y"].dim[0]
        coeff = float(N) / float(Y.shape[0])

        # Compute parameter updates
        self._updateParameters(Y, Z, tau, mask, Alpha, Qmean_S1, Qvar_S1, Qvar_S0, Qtheta, SW, theta_lnE, theta_lnEInv, coeff, ro)
    
    def _updateParameters(self, Y, Z, tau, mask, Alpha, Qmean_S1, Qvar_S1, Qvar_S0, Qtheta, SW, theta_lnE, theta_lnEInv, coeff, ro):

        # Mask matrices
        tau[mask] = 0.

        # Copy matrices to GPU
        tau_gpu = gpu_utils.array(tau)

        # precompute terms
        tauYT = (tau_gpu*gpu_utils.array(Y)).T

        # Update each latent variable in turn
        for k in range(self.dim[1]):

            # Copy matrices to GPU
            Zk_cp = gpu_utils.array(Z["E"][:,k])
            ZZk_cp = gpu_utils.array(Z["E2"][:,k])
            alphak_cp = gpu_utils.array(Alpha[:,k])

            # Compute terms
            term1 = (theta_lnE-theta_lnEInv)[:,k]

            term2 = gpu_utils.asnumpy(0.5*gpu_utils.log(alphak_cp))

            term3 = gpu_utils.asnumpy(0.5 * coeff * gpu_utils.log(gpu_utils.dot(ZZk_cp, tau_gpu) + alphak_cp))

            term4_tmp1 = gpu_utils.dot(tauYT, Zk_cp)
            term4_tmp2_1 = gpu_utils.array(SW[:,s.arange(self.dim[1])!=k].T)
            term4_tmp2_2 = (Zk_cp * gpu_utils.array(Z['E'][:,s.arange(self.dim[1])!=k]).T).T
            term4_tmp2 = (tau_gpu*gpu_utils.dot(term4_tmp2_2, term4_tmp2_1)).sum(axis=0)
            term4_tmp3 = gpu_utils.dot(ZZk_cp.T,tau_gpu) + alphak_cp
            term4 = coeff * gpu_utils.asnumpy(0.5*gpu_utils.divide(gpu_utils.square(term4_tmp1-term4_tmp2),term4_tmp3)) 

            # Update S
            Qtheta[:,k] *= (1 - ro)
            Qtheta[:,k] += ro * (1./(1.+s.exp(-(term1+term2-term3+term4))))

            # Update W
            tmp_var = gpu_utils.asnumpy(1./term4_tmp3)
            Qvar_S1[:,k] *= (1 - ro)
            Qvar_S1[:,k] += ro * tmp_var

            Qmean_S1[:,k] *= (1 - ro)
            Qmean_S1[:,k] += ro * tmp_var * gpu_utils.asnumpy(term4_tmp1-term4_tmp2)

            # Update Expectations for the next iteration
            SW[:,k] = Qtheta[:,k] * Qmean_S1[:,k]

        # update of Qvar_S0
        Qvar_S0 *= (1 - ro)
        Qvar_S0 += ro/Alpha

        # Save updated parameters of the Q distribution
        self.Q.setParameters(mean_B0=s.zeros((self.dim[0],self.dim[1])), var_B0=Qvar_S0, mean_B1=Qmean_S1, var_B1=Qvar_S1, theta=Qtheta)

    def calculateELBO(self):
        # Collect parameters and expectations
        Qpar,Qexp = self.Q.getParameters(), self.Q.getExpectations()
        S,WW = Qexp["EB"], Qexp["ENN"]
        Qvar = Qpar['var_B1']
        theta = self.markov_blanket["ThetaW"].getExpectations(expand=True)
        if "AlphaW" in self.markov_blanket:
            alpha = self.markov_blanket["AlphaW"].getExpectations(expand=True)
        else:
            alpha = dict()
            alpha['E'] = 1./self.P.params['var_B1']
            alpha['lnE'] = s.log(1./self.P.params['var_B1'])

        # Calculate ELBO term for W
        lb_pw = (alpha["lnE"].sum() - s.sum(alpha["E"]*WW))/2.
        lb_qw = -0.5*self.dim[1]*self.dim[0] - 0.5*(S*s.log(Qvar) + (1.-S)*s.log(1./alpha["E"])).sum()
        lb_w = lb_pw - lb_qw

        # Calculate ELBO term for S
        # S[S<1e-10] = 1e-10
        # S[S>0.9999999] = 0.9999999
        lb_ps = S*theta['lnE'] + (1.-S)*theta['lnEInv']
        lb_qs = S*s.log(S) + (1.-S)*s.log(1.-S)

        # Replace NAs (due to theta=1) with zeros
        lb_ps[s.isnan(lb_ps)] = 0.
        lb_qs[s.isnan(lb_qs)] = 0.

        lb_s = s.sum(lb_ps) - s.sum(lb_qs)

        return lb_w + lb_s
