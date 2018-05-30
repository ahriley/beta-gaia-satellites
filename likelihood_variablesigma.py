import numpy as np
import matplotlib.pyplot as plt
import scipy.optimize as op
import emcee
import corner
import yaml

# get indices of unwanted satellites
dwarf_file = 'data/dwarfs/fritz.yaml'
with open(dwarf_file, 'r') as f:
    dwarfs = yaml.load(f)
names = list(dwarfs.keys())
ignore = [names.index('Cra I'), names.index('Eri II'), names.index('Phe I')]

# load MC samples, remove unwanted satellites
MC_dwarfs = np.load('data/mcmc/sampling_converted_fritz.npy')
dists = MC_dwarfs[:,:,6]
MC_dwarfs = MC_dwarfs[:,:,9:12]
MC_dwarfs = np.swapaxes(MC_dwarfs,0,1)
MC_dwarfs = np.delete(MC_dwarfs, ignore, axis=0)

# data and covariances for each satellite
vels = np.mean(MC_dwarfs, axis=1)
vel_covs = np.array([np.cov(np.swapaxes(dwarf,0,1)) for dwarf in MC_dwarfs])
dists = np.mean(np.delete(np.swapaxes(dists,0,1), ignore, axis=0), axis=1)

# variable dispersions with distance
def sigma(r, sigma0, r0, alpha):
    return sigma0*(1+(r/r0))**-alpha

# Likelihood
def lnlike(theta, data, data_covs, data_dists):
    shifts = data - theta[:3]
    s0s, r0s, alphas = 10**theta[3:6], theta[6:9], theta[9:12]
    sigmas = np.array([sigma(r,s0s,r0s,alphas) for r in data_dists])
    cov_theta = np.array([np.diag(sig**2) for sig in sigmas])
    covs = data_covs + cov_theta
    icovs = np.linalg.inv(covs)
    lnlike = np.sum([shift@(icov@shift) for shift,icov in zip(shifts,icovs)])
    lnlike += np.sum(np.log(np.linalg.det(covs)))
    return -lnlike

# Prior (flat)
def lnprior(theta):
    m = theta[:3]
    lns0, r0, a = theta[3:6], theta[6:9], theta[9:12]
    if ((m<500).all() and (m>-500).all() and (lns0>-3).all() and (lns0<3).all()
        and (r0>10).all() and (r0<300).all() and (a>0).all() and (a<10).all()):
        return 0.0
    return -np.inf

# Full log-probability function (likelihood*prior)
def lnprob(theta, data, data_covs, data_dists):
    lp = lnprior(theta)
    if not np.isfinite(lp):
        return -np.inf
    return lp + lnlike(theta, data, data_covs, data_dists)

# Initialize walkers by randomly sampling prior
ndim, nwalkers = 12, 100
p_scale = np.array([1000,1000,1000,6,6,6,290,290,290,10,10,10])
p_shift = np.array([500,500,500,3,3,3,-10,-10,-10,0,0,0])
p0 = [np.random.uniform(size=ndim)*p_scale - p_shift for i in range(nwalkers)]

# Set up and run MCMC
sampler = emcee.EnsembleSampler(nwalkers, ndim, lnprob, args=(vels, vel_covs, dists))
pos, prob, state = sampler.run_mcmc(p0, 500)

# Look by eye at the burn-in
stepnum = np.arange(0,500,1)+1
stepnum = np.array([stepnum for i in range(nwalkers)])
plt.plot(stepnum, sampler.chain[:,:,0]);

print("Mean acceptance fraction: {0:.3f}"
                .format(np.mean(sampler.acceptance_fraction)))

# if needed, reset and run chain for new sample
sampler.reset()
pos, prob, state = sampler.run_mcmc(pos, 500)

# Flatten the chain and remove burn-in
burnin = 0
samples = sampler.chain[:, burnin:, :].reshape((-1, ndim))
samples[:,3:6] = 10**samples[:,3:6]

# Make corner plot
fig = corner.corner(samples, labels=[r"$v_r$", r"$v_\theta$", r"$v_\phi$",
                        r"$\sigma_r$", r"$\sigma_\theta$", r"$\sigma_\phi$",
                        r"$r_{0,r}$", r"$r_{0,\theta}$", r"$r_{0,\phi}$",
                        r"$\alpha_r$", r"$\alpha_\theta$", r"$\alpha_\phi$"],
                      quantiles=[0.16, 0.5, 0.84],
                      show_titles=True, title_kwargs={"fontsize": 12})

fig.savefig('figures/likelihood_variablesigma_constrainedprior.png', bbox_inches='tight')
np.save('data/mcmc/mcmc_variablesigma_constrainedprior', samples, allow_pickle=False)

"""
samples[:, 2] = np.exp(samples[:, 2])
vr_mcmc, vtheta_mcmc, vphi_mcmc, sigr_mcmc, sigtheta_mcmc, sigphi_mcmc = map(lambda v: (v[1], v[2]-v[1], v[1]-v[0]),
                             zip(*np.percentile(samples, [16, 50, 84],
                                                axis=0)))
"""
