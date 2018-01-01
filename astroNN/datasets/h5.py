# ---------------------------------------------------------#
#   astroNN.datasets.h5: compile h5 files for NN
# ---------------------------------------------------------#

import os
import time
from functools import reduce

import h5py
import numpy as np
from astropy.io import fits

import astroNN.apogee.downloader
import astroNN.datasets.xmatch
from astroNN.apogee.apogee_shared import apogee_env, apogee_default_dr
from astroNN.apogee.chips import chips_pix_info
from astroNN.apogee.chips import gap_delete, continuum
from astroNN.apogee.downloader import combined_spectra, visit_spectra
from astroNN.gaia.downloader import tgas_load, anderson_2017_parallax
from astroNN.gaia.gaia_shared import gaia_env
from astroNN.models.models_shared import target_conversion
from astroNN.shared.nn_tools import h5name_check

currentdir = os.getcwd()
_APOGEE_DATA = apogee_env()
_GAIA_DATA = gaia_env()


class H5Compiler():
    """
    A class for compiling h5 dataset for Keras to use
    """

    def __init__(self):
        self.apogee_dr = None
        self.gaia_dr = None
        self.starflagcut = True
        self.aspcapflagcut = True
        self.vscattercut = 1
        self.teff_high = 5500
        self.teff_low = 4000
        self.SNR_low = 100
        self.SNR_high = 99999
        self.ironlow = -3
        self.filename = None
        self.spectra_only = False
        self.cont_mask = None  # Continuum Mask
        self.use_apogee = True
        self.use_esa_gaia = False
        self.use_anderson_2017 = True
        self.err_info = True  # Whether to include error information in h5 dataset
        self.continuum = True  # True to do continuum normalization, False to use aspcap normalized spectra

    def load_allstar(self):
        self.apogee_dr = apogee_default_dr(dr=self.apogee_dr)
        allstarpath = astroNN.apogee.downloader.allstar(dr=self.apogee_dr)
        hdulist = fits.open(allstarpath)
        print('Loading allStar DR{} catalog'.format(self.apogee_dr))
        return hdulist

    def filter_apogeeid_list(self, hdulist):
        vscatter = hdulist[1].data['VSCATTER']
        SNR = hdulist[1].data['SNR']
        location_id = hdulist[1].data['LOCATION_ID']
        teff = hdulist[1].data['PARAM'][:, 0]
        Fe = hdulist[1].data['X_H'][:, 17]
        logg = hdulist[1].data['LOGG']
        K = hdulist[1].data['K']

        total = range(len(SNR))

        if self.starflagcut is True:
            starflag = hdulist[1].data['STARFLAG']
            fitlered_starflag = np.where(starflag == 0)[0]
        else:
            fitlered_starflag = total

        if self.aspcapflagcut is True:
            aspcapflag = hdulist[1].data['ASPCAPFLAG']
            fitlered_aspcapflag = np.where(aspcapflag == 0)[0]
        else:
            fitlered_aspcapflag = total

        fitlered_temp_lower = np.where((self.teff_low <= teff))[0]
        fitlered_temp_upper = np.where((self.teff_high >= teff))[0]
        fitlered_vscatter = np.where(vscatter < self.vscattercut)[0]
        fitlered_logg = np.where(logg != -9999)[0]
        fitlered_Fe = np.where(Fe > self.ironlow)[0]
        fitlered_snrlow = np.where(SNR > self.SNR_low)[0]
        fitlered_snrhigh = np.where(SNR < self.SNR_high)[0]
        fitlered_K = np.where(K != -9999)[0]
        fitlered_location = np.where(location_id > 1)[0]

        filtered_index = reduce(np.intersect1d,
                                (fitlered_starflag, fitlered_aspcapflag, fitlered_temp_lower, fitlered_vscatter,
                                 fitlered_Fe, fitlered_snrlow, fitlered_snrhigh, fitlered_location, fitlered_temp_upper,
                                 fitlered_K, fitlered_logg))

        print('Total Combined Spectra after filtering: ', filtered_index.shape[0])
        print('Total Individual Visit Spectra there: ', np.sum(hdulist[1].data['NVISITS'][filtered_index]))

        return filtered_index

    def apstar_normalization(self, spectra, spectra_err):
        return continuum(spectra=spectra, spectra_vars=spectra_err, cont_mask=self.cont_mask, deg=2, dr=self.apogee_dr)

    def compile(self):
        h5name_check(self.filename)

        hdulist = self.load_allstar()
        indices = self.filter_apogeeid_list(hdulist)

        info = chips_pix_info(dr=self.apogee_dr)
        total_pix = (info[1] - info[0]) + (info[3] - info[2]) + (info[5] - info[4])
        default_length = 900000

        spec = np.zeros((default_length, total_pix), dtype=np.float32)
        spec_err = np.zeros((default_length, total_pix), dtype=np.float32)
        RA = np.zeros(default_length, dtype=np.float32)
        DEC = np.zeros(default_length, dtype=np.float32)
        SNR = np.zeros(default_length, dtype=np.float32)
        individual_flag = np.zeros(default_length, dtype=np.float32)
        Kmag = np.zeros(default_length, dtype=np.float32)

        # Data array
        teff = np.zeros(default_length, dtype=np.float32)
        logg = np.zeros(default_length, dtype=np.float32)
        MH = np.zeros(default_length, dtype=np.float32)
        alpha_M = np.zeros(default_length, dtype=np.float32)
        C = np.zeros(default_length, dtype=np.float32)
        C1 = np.zeros(default_length, dtype=np.float32)
        N = np.zeros(default_length, dtype=np.float32)
        O = np.zeros(default_length, dtype=np.float32)
        Na = np.zeros(default_length, dtype=np.float32)
        Mg = np.zeros(default_length, dtype=np.float32)
        Al = np.zeros(default_length, dtype=np.float32)
        Si = np.zeros(default_length, dtype=np.float32)
        P = np.zeros(default_length, dtype=np.float32)
        S = np.zeros(default_length, dtype=np.float32)
        K = np.zeros(default_length, dtype=np.float32)
        Ca = np.zeros(default_length, dtype=np.float32)
        Ti = np.zeros(default_length, dtype=np.float32)
        Ti2 = np.zeros(default_length, dtype=np.float32)
        V = np.zeros(default_length, dtype=np.float32)
        Cr = np.zeros(default_length, dtype=np.float32)
        Mn = np.zeros(default_length, dtype=np.float32)
        Fe = np.zeros(default_length, dtype=np.float32)
        Co = np.zeros(default_length, dtype=np.float32)
        Ni = np.zeros(default_length, dtype=np.float32)
        Cu = np.zeros(default_length, dtype=np.float32)
        Ge = np.zeros(default_length, dtype=np.float32)
        Ce = np.zeros(default_length, dtype=np.float32)
        Rb = np.zeros(default_length, dtype=np.float32)
        Y = np.zeros(default_length, dtype=np.float32)
        Nd = np.zeros(default_length, dtype=np.float32)
        parallax = np.zeros(default_length, dtype=np.float32)
        fakemag = np.zeros(default_length, dtype=np.float32)


        # Error array
        teff_err = np.zeros(default_length, dtype=np.float32)
        logg_err = np.zeros(default_length, dtype=np.float32)
        MH_err = np.zeros(default_length, dtype=np.float32)
        alpha_M_err = np.zeros(default_length, dtype=np.float32)
        C_err = np.zeros(default_length, dtype=np.float32)
        C1_err = np.zeros(default_length, dtype=np.float32)
        N_err = np.zeros(default_length, dtype=np.float32)
        O_err = np.zeros(default_length, dtype=np.float32)
        Na_err = np.zeros(default_length, dtype=np.float32)
        Mg_err = np.zeros(default_length, dtype=np.float32)
        Al_err = np.zeros(default_length, dtype=np.float32)
        Si_err = np.zeros(default_length, dtype=np.float32)
        P_err = np.zeros(default_length, dtype=np.float32)
        S_err = np.zeros(default_length, dtype=np.float32)
        K_err = np.zeros(default_length, dtype=np.float32)
        Ca_err = np.zeros(default_length, dtype=np.float32)
        Ti_err = np.zeros(default_length, dtype=np.float32)
        Ti2_err = np.zeros(default_length, dtype=np.float32)
        V_err = np.zeros(default_length, dtype=np.float32)
        Cr_err = np.zeros(default_length, dtype=np.float32)
        Mn_err = np.zeros(default_length, dtype=np.float32)
        Fe_err = np.zeros(default_length, dtype=np.float32)
        Co_err = np.zeros(default_length, dtype=np.float32)
        Ni_err = np.zeros(default_length, dtype=np.float32)
        Cu_err = np.zeros(default_length, dtype=np.float32)
        Ge_err = np.zeros(default_length, dtype=np.float32)
        Ce_err = np.zeros(default_length, dtype=np.float32)
        Rb_err = np.zeros(default_length, dtype=np.float32)
        Y_err = np.zeros(default_length, dtype=np.float32)
        Nd_err = np.zeros(default_length, dtype=np.float32)
        parallax_err = np.zeros(default_length, dtype=np.float32)
        fakemag_err = np.zeros(default_length, dtype=np.float32)

        array_counter = 0

        start_time = time.time()

        for counter, index in enumerate(indices):
            nvisits = 1
            apogee_id = hdulist[1].data['APOGEE_ID'][index]
            location_id = hdulist[1].data['LOCATION_ID'][index]
            if counter % 100 == 0:
                print('Completed {} of {}, {:.03f} seconds elapsed'.format(counter, indices.shape[0],
                                                                           time.time() - start_time))
            if self.continuum is False:
                warningflag, path = combined_spectra(dr=self.apogee_dr, location=location_id, apogee=apogee_id,
                                                     verbose=0)
                if warningflag is None:
                    combined_file = fits.open(path)
                    _spec = combined_file[1].data  # Pseudo-continuum normalized flux
                    _spec_err = combined_file[2].data  # Spectrum error array
                    _spec = gap_delete(_spec, dr=self.apogee_dr)  # Delete the gap between sensors
                    _spec_err = gap_delete(_spec_err, dr=self.apogee_dr)
                    combined_file.close()
            else:
                warningflag, apstar_path = visit_spectra(dr=self.apogee_dr, location=location_id, apogee=apogee_id,
                                                         verbose=0)
                apstar_file = fits.open(apstar_path)
                nvisits = apstar_file[0].header['NVISITS']
                if nvisits == 1:
                    _spec = apstar_file[1].data
                    _spec_err = apstar_file[2].data
                else:
                    _spec = apstar_file[1].data[1:]
                    _spec_err = apstar_file[2].data[1:]
                    nvisits += 1
                _spec = gap_delete(_spec, dr=self.apogee_dr)
                _spec_err = gap_delete(_spec_err, dr=self.apogee_dr)
                _spec, _spec_err = self.apstar_normalization(_spec, _spec_err)
                apstar_file.close()

            if warningflag is None:
                if nvisits == 1:
                    individual_flag[array_counter:array_counter + nvisits] = 0
                else:
                    individual_flag[array_counter:array_counter + 1] = 0
                    individual_flag[array_counter + 1:array_counter + nvisits] = 1
                spec[array_counter:array_counter + nvisits, :] = _spec
                spec_err[array_counter:array_counter + nvisits, :] = _spec_err
                SNR[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['SNR'][index], nvisits)
                RA[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['RA'][index], nvisits)
                DEC[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['DEC'][index], nvisits)
                parallax[array_counter:array_counter + nvisits] = np.tile(-9999, nvisits)
                parallax_err[array_counter:array_counter + nvisits] = np.tile(-9999, nvisits)
                fakemag[array_counter:array_counter + nvisits] = np.tile(-9999, nvisits)
                fakemag_err[array_counter:array_counter + nvisits] = np.tile(-9999, nvisits)
                Kmag[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['K'][index], nvisits)

                if self.spectra_only is not True:
                    teff[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['PARAM'][index, 0], nvisits)
                    logg[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['PARAM'][index, 1], nvisits)
                    MH[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['PARAM'][index, 3], nvisits)
                    alpha_M[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['PARAM'][index, 6],
                                                                             nvisits)
                    C[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 0], nvisits)
                    C1[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 1], nvisits)
                    N[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 2], nvisits)
                    O[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 3], nvisits)
                    Na[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 4], nvisits)
                    Mg[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 5], nvisits)
                    Al[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 6], nvisits)
                    Si[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 7], nvisits)
                    P[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 8], nvisits)
                    S[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 9], nvisits)
                    K[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 10], nvisits)
                    Ca[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 11], nvisits)
                    Ti[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 12], nvisits)
                    Ti2[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 13], nvisits)
                    V[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 14], nvisits)
                    Cr[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 15], nvisits)
                    Mn[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 16], nvisits)
                    Fe[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 17], nvisits)
                    Co[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 18], nvisits)
                    Ni[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 19], nvisits)
                    Cu[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 20], nvisits)
                    Ge[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 21], nvisits)
                    Ce[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 22], nvisits)
                    Rb[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 23], nvisits)
                    Y[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 24], nvisits)
                    Nd[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H'][index, 25], nvisits)

                    teff_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['PARAM_COV'][index, 0, 0],
                                                                              nvisits)
                    logg_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['PARAM_COV'][index, 1, 1],
                                                                              nvisits)
                    MH_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['PARAM_COV'][index, 3, 3],
                                                                            nvisits)
                    alpha_M_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['PARAM_COV'][index, 6, 6], nvisits)
                    C_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 0],
                                                                           nvisits)
                    C1_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 1],
                                                                            nvisits)
                    N_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 2],
                                                                           nvisits)
                    O_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 3],
                                                                           nvisits)
                    Na_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 4],
                                                                            nvisits)
                    Mg_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 5],
                                                                            nvisits)
                    Al_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 6],
                                                                            nvisits)
                    Si_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 7],
                                                                            nvisits)
                    P_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 8],
                                                                           nvisits)
                    S_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 9],
                                                                           nvisits)
                    K_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 10],
                                                                           nvisits)
                    Ca_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 11],
                                                                            nvisits)
                    Ti_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 12],
                                                                            nvisits)
                    Ti2_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 13],
                                                                             nvisits)
                    V_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 14],
                                                                           nvisits)
                    Cr_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 15],
                                                                            nvisits)
                    Mn_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 16],
                                                                            nvisits)
                    Fe_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 17],
                                                                            nvisits)
                    Co_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 18],
                                                                            nvisits)
                    Ni_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 19],
                                                                            nvisits)
                    Cu_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 20],
                                                                            nvisits)
                    Ge_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 21],
                                                                            nvisits)
                    Ce_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 22],
                                                                            nvisits)
                    Rb_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 23],
                                                                            nvisits)
                    Y_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 24],
                                                                           nvisits)
                    Nd_err[array_counter:array_counter + nvisits] = np.tile(hdulist[1].data['X_H_ERR'][index, 25],
                                                                            nvisits)
                array_counter += nvisits

        spec = spec[0:array_counter]
        spec_err = spec_err[0:array_counter]
        individual_flag = individual_flag[0:array_counter]
        RA = RA[0:array_counter]
        DEC = DEC[0:array_counter]
        SNR = SNR[0:array_counter]

        if self.spectra_only is not True:
            teff = teff[0:array_counter]
            logg = logg[0:array_counter]
            Kmag = Kmag[0:array_counter]
            MH = MH[0:array_counter]
            alpha_M = alpha_M[0:array_counter]
            C = C[0:array_counter]
            C1 = C1[0:array_counter]
            N = N[0:array_counter]
            O = O[0:array_counter]
            Na = Na[0:array_counter]
            Mg = Mg[0:array_counter]
            Al = Al[0:array_counter]
            Si = Si[0:array_counter]
            P = P[0:array_counter]
            S = S[0:array_counter]
            K = K[0:array_counter]
            Ca = Ca[0:array_counter]
            Ti = Ti[0:array_counter]
            Ti2 = Ti2[0:array_counter]
            V = V[0:array_counter]
            Cr = Cr[0:array_counter]
            Mn = Mn[0:array_counter]
            Fe = Fe[0:array_counter]
            Co = Co[0:array_counter]
            Ni = Ni[0:array_counter]
            Cu = Cu[0:array_counter]
            Ge = Ge[0:array_counter]
            Ce = Ce[0:array_counter]
            Rb = Rb[0:array_counter]
            Y = Y[0:array_counter]
            Nd = Nd[0:array_counter]
            parallax = parallax[0:array_counter]
            fakemag = fakemag[0:array_counter]

            teff_err = teff_err[0:array_counter]
            logg_err = logg_err[0:array_counter]
            MH_err = MH_err[0:array_counter]
            alpha_M_err = alpha_M_err[0:array_counter]
            C_err = C_err[0:array_counter]
            C1_err = C1_err[0:array_counter]
            N_err = N_err[0:array_counter]
            O_err = O_err[0:array_counter]
            Na_err = Na_err[0:array_counter]
            Mg_err = Mg_err[0:array_counter]
            Al_err = Al_err[0:array_counter]
            Si_err = Si_err[0:array_counter]
            P_err = P_err[0:array_counter]
            S_err = S_err[0:array_counter]
            K_err = K_err[0:array_counter]
            Ca_err = Ca_err[0:array_counter]
            Ti_err = Ti_err[0:array_counter]
            Ti2_err = Ti2_err[0:array_counter]
            V_err = V_err[0:array_counter]
            Cr_err = Cr_err[0:array_counter]
            Mn_err = Mn_err[0:array_counter]
            Fe_err = Fe_err[0:array_counter]
            Co_err = Co_err[0:array_counter]
            Ni_err = Ni_err[0:array_counter]
            Cu_err = Cu_err[0:array_counter]
            Ge_err = Ge_err[0:array_counter]
            Ce_err = Ce_err[0:array_counter]
            Rb_err = Rb_err[0:array_counter]
            Y_err = Y_err[0:array_counter]
            Nd_err = Nd_err[0:array_counter]
            parallax_err = parallax_err[0:array_counter]
            fakemag_err = fakemag_err[0:array_counter]

            if self.use_anderson_2017 is True:
                gaia_ra, gaia_dec, gaia_parallax, gaia_var = anderson_2017_parallax(mode='r')
                nan_index = np.argwhere(np.isnan(gaia_parallax))
                gaia_ra = np.delete(gaia_ra, nan_index)
                gaia_dec = np.delete(gaia_dec, nan_index)
                gaia_parallax = np.delete(gaia_parallax, nan_index)
                gaia_var = np.delete(gaia_var, nan_index)
                m1, m2, sep = astroNN.datasets.xmatch.xmatch(RA, gaia_ra, maxdist=2, colRA1=RA, colDec1=DEC,
                                                             epoch1=2000.,
                                                             colRA2=gaia_ra, colDec2=gaia_dec, epoch2=2000., swap=False)
            elif self.use_esa_gaia is True:
                esa_tgas = tgas_load(compact=True)
                gaia_ra = esa_tgas[0]
                gaia_dec = esa_tgas[1]
                gaia_parallax = esa_tgas[4]
                gaia_var = esa_tgas[5]
                m1, m2, sep = astroNN.datasets.xmatch.xmatch(RA, gaia_ra, maxdist=2, colRA1=RA, colDec1=DEC,
                                                             epoch1=2000.,
                                                             colRA2=gaia_ra, colDec2=gaia_dec, epoch2=2015.,
                                                             colpmRA2=esa_tgas[2], colpmDec2=esa_tgas[3], swap=False)
            if self.use_anderson_2017 is True or self.use_esa_gaia is True:
                parallax[m1] = gaia_parallax[m2]
                parallax_err[m1] = gaia_var[m2]

                fakemag[m1] = Kmag[m1] / gaia_parallax[m2]
                fakemag_err[m1] = np.abs((parallax_err[m1] / gaia_parallax[m2]) * fakemag[m1])

        print('Creating {}.h5'.format(self.filename))
        h5f = h5py.File('{}.h5'.format(self.filename), 'w')
        h5f.create_dataset('spectra', data=spec)
        h5f.create_dataset('spectra_err', data=spec_err)
        h5f.create_dataset('in_flag', data=individual_flag)
        h5f.create_dataset('index', data=indices)

        if self.spectra_only is not True:
            h5f.create_dataset('SNR', data=SNR)
            h5f.create_dataset('RA', data=RA)
            h5f.create_dataset('DEC', data=DEC)
            h5f.create_dataset('Kmag', data=Kmag)
            h5f.create_dataset('teff', data=teff)
            h5f.create_dataset('logg', data=logg)
            h5f.create_dataset('M', data=MH)
            h5f.create_dataset('alpha', data=alpha_M)
            h5f.create_dataset('C', data=C)
            h5f.create_dataset('C1', data=C1)
            h5f.create_dataset('N', data=N)
            h5f.create_dataset('O', data=O)
            h5f.create_dataset('Na', data=Na)
            h5f.create_dataset('Mg', data=Mg)
            h5f.create_dataset('Al', data=Al)
            h5f.create_dataset('Si', data=Si)
            h5f.create_dataset('P', data=P)
            h5f.create_dataset('S', data=S)
            h5f.create_dataset('K', data=K)
            h5f.create_dataset('Ca', data=Ca)
            h5f.create_dataset('Ti', data=Ti)
            h5f.create_dataset('Ti2', data=Ti2)
            h5f.create_dataset('V', data=V)
            h5f.create_dataset('Cr', data=Cr)
            h5f.create_dataset('Mn', data=Mn)
            h5f.create_dataset('Fe', data=Fe)
            h5f.create_dataset('Co', data=Co)
            h5f.create_dataset('Ni', data=Ni)
            h5f.create_dataset('Cu', data=Cu)
            h5f.create_dataset('Ge', data=Ge)
            h5f.create_dataset('Ce', data=Ce)
            h5f.create_dataset('Rb', data=Rb)
            h5f.create_dataset('Y', data=Y)
            h5f.create_dataset('Nd', data=Nd)
            h5f.create_dataset('parallax', data=parallax)
            h5f.create_dataset('fakemag', data=fakemag)

            h5f.create_dataset('teff_err', data=teff_err)
            h5f.create_dataset('logg_err', data=logg_err)
            h5f.create_dataset('M_err', data=MH_err)
            h5f.create_dataset('alpha_err', data=alpha_M_err)
            h5f.create_dataset('C_err', data=C_err)
            h5f.create_dataset('C1_err', data=C1_err)
            h5f.create_dataset('N_err', data=N_err)
            h5f.create_dataset('O_err', data=O_err)
            h5f.create_dataset('Na_err', data=Na_err)
            h5f.create_dataset('Mg_err', data=Mg_err)
            h5f.create_dataset('Al_err', data=Al_err)
            h5f.create_dataset('Si_err', data=Si_err)
            h5f.create_dataset('P_err', data=P_err)
            h5f.create_dataset('S_err', data=S_err)
            h5f.create_dataset('K_err', data=K_err)
            h5f.create_dataset('Ca_err', data=Ca_err)
            h5f.create_dataset('Ti_err', data=Ti_err)
            h5f.create_dataset('Ti2_err', data=Ti2_err)
            h5f.create_dataset('V_err', data=V_err)
            h5f.create_dataset('Cr_err', data=Cr_err)
            h5f.create_dataset('Mn_err', data=Mn_err)
            h5f.create_dataset('Fe_err', data=Fe_err)
            h5f.create_dataset('Co_err', data=Co_err)
            h5f.create_dataset('Ni_err', data=Ni_err)
            h5f.create_dataset('Cu_err', data=Cu_err)
            h5f.create_dataset('Ge_err', data=Ge_err)
            h5f.create_dataset('Ce_err', data=Ce_err)
            h5f.create_dataset('Rb_err', data=Rb_err)
            h5f.create_dataset('Y_err', data=Y_err)
            h5f.create_dataset('Nd_err', data=Nd_err)
            h5f.create_dataset('parallax_err', data=parallax_err)
            h5f.create_dataset('fakemag_err', data=fakemag_err)

        h5f.close()
        print('Successfully created {}.h5 in {}'.format(self.filename, currentdir))


class H5Loader(object):
    def __init__(self, filename):
        self.filename = filename
        self.target = 'all'
        self.currentdir = os.getcwd()
        self.load_combined = True
        self.exclude9999 = False

    def load(self):
        if os.path.isfile(os.path.join(self.currentdir, self.filename)) is True:
            h5data = os.path.join(self.currentdir, self.filename)
        elif os.path.isfile(os.path.join(self.currentdir, (self.filename + '.h5'))) is True:
            h5data = os.path.join(self.currentdir, (self.filename + '.h5'))
        else:
            raise FileNotFoundError('Cannot find {}'.format(os.path.join(self.currentdir, self.filename)))

        self.target = target_conversion(self.target)
        with h5py.File(h5data) as F:  # ensure the file will be cleaned up
            if self.exclude9999 is True:
                index_not9999 = []
                for counter, tg in enumerate(self.target):
                    temp = np.array(F['{}'.format(tg)])
                    temp_index = np.where(temp != -9999)
                    if counter == 0:
                        index_not9999 = temp_index
                    else:
                        index_not9999 = reduce(np.intersect1d, (index_not9999, temp_index))

                in_flag = index_not9999
                if self.load_combined is True:
                    in_flag = np.where(np.array(F['in_flag']) == 0)
                elif self.load_combined is False:
                    in_flag = np.where(np.array(F['in_flag']) == 1)

                index_not9999_flag = reduce(np.intersect1d, (index_not9999, in_flag))

                spectra = np.array(F['spectra'])[index_not9999_flag]

                y = np.array((spectra.shape[1]))
                for counter, tg in enumerate(self.target):
                    temp = np.array(F['{}'.format(tg)])
                    temp = temp[index_not9999_flag]
                    if counter == 0:
                        y = temp[:]
                    else:
                        y = np.column_stack((y, temp[:]))
            else:
                if self.load_combined is True:
                    in_flag = np.where(np.array(F['in_flag']) == 0)
                elif self.load_combined is False:
                    in_flag = np.where(np.array(F['in_flag']) == 1)

                spectra = np.array(F['spectra'])[in_flag]

                y = np.array((spectra.shape[1]))
                for counter, tg in enumerate(self.target):
                    temp = np.array(F['{}'.format(tg)])
                    temp = temp[in_flag]
                    if counter == 0:
                        y = temp[:]
                    else:
                        y = np.column_stack((y, temp[:]))
            F.close()

        return spectra, y
