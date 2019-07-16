import os
import numpy as np
import time
import torch
torch.set_default_tensor_type('torch.FloatTensor')
from torchvision import datasets, transforms
from torchvision.datasets import ImageFolder
from torchvision.datasets.mnist import MNIST as MNIST_dataset
from torch.utils.data import TensorDataset, DataLoader
from torch.autograd import Variable
import torchvision
import torch.optim as optim
import torch.nn.functional as F
import torch.nn as nn
from display import Display, minmax
from retina_copie import Retina
import MotionClouds as mc
from display import pe, minmax
from PIL import Image
import SLIP
#from what import What # l'entrainement du reseau what done 11% de reussite
from what import What # on va voir si ça donne la meme chose avec un robust_what
# from tqdm import tqdm # commenter car ne sert pas et sinon hydra ne veut pas
import matplotlib.pyplot as plt
from skimage import io
from PIL import Image

import datetime

'''
MNIST(MNIST_dataset):
    def __getitem__(self, index):
        """
        Args:
            index (int): Index

        Returns:
            tuple: (image, target) where target is index of the target class.
        """
        if self.train:
            img, target = self.train_data[index], self.train_labels[index]
        else:
            img, target = self.test_data[index], self.test_labels[index]

        # doing this so that it is consistent with all other datasets
        # to return a PIL Image
        img = Image.fromarray(img.numpy(), mode='L')

        if self.transform is not None:
            img = self.transform((img, index))

        if self.target_transform is not None:
            target = self.target_transform((target, index))

        return img, target
'''


class ChicagoFacesDataset:
    """Chicago Faces dataset."""

    def __init__(self, csv_file, root_dir, transform):
        """
        Args:
            csv_file (string): Path to the csv file with annotations.
            root_dir (string): Directory with all the images.
        """
        self.root_dir = root_dir
        self.init_get_path_files()
        self.transform = transform

    def init_get_path_files(self):
        self.list_files = []
        self.dic_sample = {}
        folder_directory = self.root_dir

        for path, subdirs, files in os.walk(folder_directory):
            for name in files:
                if name[-4:] == '.jpg':
                    # print(path, name)
                    self.list_files.append(os.path.join(path, name))
        # print(self.list_files)

    def __len__(self):
        return len(self.list_files)

    def __getitem__(self, idx):
        # img_name = os.path.join(self.root_dir, self.landmarks_frame.iloc[idx, 0])
        img_name = os.path.join(self.list_files[idx])
        #image = io.imread(img_name, as_gray=True) # commente le 08/07/2019 le gris sera fait dans
        image = io.imread(img_name)
        if self.transform is not None:
            image = self.transform(image)
        name_image = self.list_files[idx][-28:-4]
        target = self.list_files[idx][-5:-4]
        if target == 'C' or target == 'O':
            target = self.list_files[idx][-6:-4]
        self.dic_sample[idx] = [name_image, image, target]

        return self.dic_sample[idx]


class RetinaFill:
    def __init__(self, N_pic=128, baseline=0):
        self.N_pic=N_pic
        self.baseline = baseline

    def __call__(self, sample_index):
        sample = np.array(sample_index)
        w = sample.shape[0]
        pixel_fullfield = np.ones((self.N_pic, self.N_pic)) * self.baseline
        N_mid = self.N_pic//2
        w_mid = w // 2
        pixel_fullfield[N_mid - w_mid: N_mid - w_mid + w,
                  N_mid - w_mid: N_mid - w_mid + w] = sample
        print("RetinaFill ok")
        #print(pixel_fullfield)
        return pixel_fullfield

class CollFill:
    def __init__(self, accuracy_map, N_pic=128, keep_label = False, baseline=0.):
        self.N_pic=N_pic
        self.accuracy_map = accuracy_map
        self.keep_label = keep_label
        self.baseline = baseline

    def __call__(self, data):
        acc = self.accuracy_map
        label = data[0]
        seed = data[1]
        w = acc.shape[0]
        fullfield = np.ones((self.N_pic, self.N_pic)) * self.baseline
        N_mid = self.N_pic//2
        w_mid = w // 2
        fullfield[N_mid - w_mid: N_mid - w_mid + w,
                  N_mid - w_mid: N_mid - w_mid + w] = acc
        if self.keep_label:
            return (fullfield, seed, label)
        else:
            return (fullfield, seed)

class WhereShift:
    def __init__(self, args, i_offset=None, j_offset=None, radius=None, theta=None, baseline=0., keep_label = False):
        self.args = args
        self.i_offset = i_offset
        self.j_offset = j_offset
        self.radius = radius
        self.theta = theta
        self.baseline = baseline
        self.keep_label = keep_label

    def __call__(self, data):
        #sample = np.array(sample)
        
        sample = data
        #print("WhereShift data :", data)
        #print(data[0].shape)
        if self.keep_label:
            label = data[2]
        
        #print(index)
        
        if self.i_offset is not None:
            i_offset = self.i_offset
            if self.j_offset is None:
                #j_offset_f = np.random.randn() * self.args.offset_std
                #j_offset_f = minmax(j_offset_f, self.args.offset_max)
                #j_offset = int(j_offset_f)
                j_offset = np.random.randint(- self.args.N_pic //3, self.args.N_pic //3)
            else:
                j_offset = int(self.j_offset)
        else: 
            if self.j_offset is not None:
                #i_offset_f = np.random.randn() * self.args.offset_std
                #i_offset_f = minmax(i_offset_f, self.args.offset_max)
                #i_offset = int(i_offset_f)
                i_offset = np.random.randint( - self.args.N_pic //3, self.args.N_pic //3)
            else: #self.i_offset is None and self.j_offset is None
                i_offset = np.random.randint( - self.args.N_pic //3, self.args.N_pic //3)
                j_offset = np.random.randint( - self.args.N_pic //3, self.args.N_pic //3)
                """
                if self.theta is None:
                    theta = np.random.rand() * 2 * np.pi
                    #print(theta)
                else:
                    theta = self.theta
                if self.radius is None:
                    radius_f = np.abs(np.random.randn()) * self.args.offset_std
                    radius = minmax(radius_f, self.args.offset_max)
                    #print(radius)
                else:
                    radius = self.radius
                i_offset = int(radius * np.cos(theta))
                j_offset = int(radius * np.sin(theta))
                """
                
        N_pic = sample[0].shape[0]
        fullfield = np.ones((N_pic, N_pic)) * self.baseline
        i_binf_patch = max(0, -i_offset)
        i_bsup_patch = min(N_pic, N_pic - i_offset)
        j_binf_patch = max(0, -j_offset)
        j_bsup_patch = min(N_pic, N_pic - j_offset)
        #print(N_pic, i_binf_patch, i_bsup_patch, j_binf_patch, j_bsup_patch)
        patch = sample[i_binf_patch:i_bsup_patch,
                       j_binf_patch:j_bsup_patch]

        i_binf_data = max(0, i_offset)
        i_bsup_data = min(N_pic, N_pic + i_offset)
        j_binf_data = max(0, j_offset)
        j_bsup_data = min(N_pic, N_pic + j_offset)
        fullfield[i_binf_data:i_bsup_data,
                  j_binf_data:j_bsup_data] = patch
        print("WhereShift ok")
        if self.keep_label:
            return fullfield, label, i_offset, j_offset
        else:
            #print(fullfield)
            return fullfield #.astype('B')

class WhereSquareCrop:
    def __init__(self, args):
        self.args = args

    def __call__(self, data3):
        image = data3        #print(image)
        h, w = len(image), len(image[0])
        dim = min(h, w)
        self.args.N_pic = dim
        image = image[h//2-dim//2:h//2+dim//2, w//2-dim//2:w//2+dim//2]
        print("WhereSquareCrop ok")
        #print(image)
        return image

        
def MotionCloudNoise(sf_0=0.125, B_sf=3., alpha=.0, N_pic=28, seed=42):
    mc.N_X, mc.N_Y, mc.N_frame = N_pic, N_pic, 1
    fx, fy, ft = mc.get_grids(mc.N_X, mc.N_Y, mc.N_frame)
    env = mc.envelope_gabor(fx, fy, ft, sf_0=sf_0, B_sf=B_sf, B_theta=np.inf, V_X=0., V_Y=0., B_V=0, alpha=alpha)

    z = mc.rectif(mc.random_cloud(env, seed=seed), contrast=1., method='Michelson')
    z = z.reshape((mc.N_X, mc.N_Y))
    return z, env

class RetinaBackground:
    def __init__(self, contrast=1., noise=1., sf_0=.1, B_sf=.1):
        self.contrast = contrast
        self.noise = noise
        self.sf_0 = sf_0
        self.B_sf = B_sf

    def __call__(self, sample):

        # sample from the MNIST dataset
        #data = np.array(sample)
        pixel_fullfield = sample
        N_pic = pixel_fullfield.shape[0]
        # to [0,1] interval
        if pixel_fullfield.min() != pixel_fullfield.max():
            fullfield = (pixel_fullfield - pixel_fullfield.min()) / (pixel_fullfield.max() - pixel_fullfield.min())
            fullfield = 2 * fullfield - 1  # go to [-1, 1] range
            fullfield *= self.contrast
            fullfield = fullfield / 2 + 0.5 # back to [0, 1] range
        else:
            fullfield = np.zeros((N_pic, N_pic))

        seed = hash(tuple(fullfield.flatten())) % (2 ** 31 - 1)
        background_noise, env = MotionCloudNoise(sf_0=self.sf_0,
                                         B_sf=self.B_sf,
                                         N_pic=N_pic,
                                         seed=seed)
        background_noise = 2 * background_noise - 1  # go to [-1, 1] range
        background_noise = self.noise * background_noise
        background_noise = background_noise / 2  + .5 # back to [0, 1] range
        # plt.imshow(im_noise)
        # plt.show()

        #fullfield = np.add(fullfield, background_noise)
        fullfield[fullfield<=0.5] = -np.inf
        fullfield = np.max((fullfield, background_noise), axis=0)
        
        fullfield = np.clip(fullfield, 0., 1.)
        fullfield = fullfield.reshape((N_pic, N_pic))
        #pixel_fullfield = fullfield * 255 # Back to pixels
        #print("RetinaBackground ok")
        #print(fullfield)
        return fullfield #.astype('B')  # Variable(torch.DoubleTensor(im)) #.to(self.device)

class RetinaMask:
    def __init__(self, N_pic=128):
        self.N_pic = N_pic
    def __call__(self, fullfield):
        #pixel_fullfield = np.array(sample)
        # to [0,1] interval
        if fullfield.min() != fullfield.max():
            fullfield = (fullfield - fullfield.min()) / (fullfield.max() - fullfield.min())
        else:
            fullfield = np.zeros((N_pic, N_pic))        
        # to [-0.5, 0.5] interval
        fullfield -=  0.5 #/ 255 #(data - d_min) / (d_max - d_min)
        x, y = np.mgrid[-1:1:1j * self.N_pic, -1:1:1j * self.N_pic]
        R = np.sqrt(x ** 2 + y ** 2)
        mask = 1. * (R < 1)
        #print(data.shape, mask.shape)
        #print('mask', mask.min(), mask.max(), mask[0, 0])
        fullfield *= mask.reshape((self.N_pic, self.N_pic))
        # back to [0,1]
        fullfield += 0.5
        #data *= 255
        #data = np.clip(data, 0, 255)
        print("RetinaMask ok")
        #print(type(fullfield))
        #print(fullfield)
        return fullfield #.astype('B')
    
class RetinaWhiten:
    def __init__(self, N_pic=128):
        self.N_pic = N_pic
        self.whit = SLIP.Image(pe=pe)
        self.whit.set_size((self.N_pic, self.N_pic))
        # https://github.com/bicv/SLIP/blob/master/SLIP/SLIP.py#L611
        self.K_whitening = self.whit.whitening_filt()
    def __call__(self, pixel_fullfield):
        fullfield = (pixel_fullfield - pixel_fullfield.min()) / (pixel_fullfield.max() - pixel_fullfield.min())
        fullfield = self.whit.FTfilter(fullfield, self.K_whitening) 
        #fullfield += 0.5
        #fullfield = np.clip(fullfield, 0, 1)
        print("RetinaWhiten ok")
        #print(fullfield)
        #print(type(fullfield))
        return fullfield #pixel_fullfield.astype('B')

class WhereZoom:
    def __init__(self, args):
        self.args = args
    def __call__(self, fullfield):
        #print(fullfield)
        #plt.imshow(fullfield)
        fullfield_PIL = Image.fromarray(fullfield)
        #print("fullfield", type(fullfield))
        #print("fullfield_PIL", type(fullfield_PIL))
        taille_zoom = self.args.zoom # taille en pixels de l'image reduite
        #fullfield_PIL.show()
        image_reduite = fullfield_PIL.resize((taille_zoom, taille_zoom))
        #image_reduite.show()
        WHITE = (255, 255, 255, 0)
        image_totale = Image.new('RGBA', (self.args.N_pic,self.args.N_pic), WHITE)
        box = (int(self.args.N_pic//2 - taille_zoom//2), int(self.args.N_pic//2 - taille_zoom//2), int(self.args.N_pic//2 + taille_zoom//2), int(self.args.N_pic//2 + taille_zoom//2))
        image_totale.paste(image_reduite, box)
        #image_totale.show()
        #print("image_totale", type(image_totale))
        image_totale = np.array(image_totale)
        #plt.imshow(image_totale)
        #print("image_totale", type(image_totale))
        if self.args.verbose: print("WhereZoom ok")
        return image_totale

class WhereGrey:
    def __init__(self, args):
        self.args = args
    def __call__(self, fullfield):
        #plt.imshow(fullfield)
        fullfield_PIL = Image.fromarray(fullfield)
        #fullfield_PIL.show()
        fullfield_PIL = fullfield_PIL.convert('LA')
        #fullfield_PIL.show()
        fullfield = np.array(fullfield_PIL)
        #plt.imshow(fullfield[:,:,0])
        if self.args.verbose : print("WhereGrey ok")
        return fullfield[:,:,0]

class WhereRotate:
    def __init__(self, args):
        self.args = args
    def __call__(self, fullfield):
        fullfield_PIL = Image.fromarray(fullfield).convert("RGBA")
        fullfield_PIL = fullfield_PIL.rotate(self.args.rotation)
        white_background = Image.new('RGBA', fullfield_PIL.size, (255,) * 4)
        fullfield_PIL = Image.composite(fullfield_PIL, white_background, fullfield_PIL)
        fullfield = np.array(fullfield_PIL)
        if self.args.verbose : print("WhereRotate ok")
        return fullfield

class FullfieldRetinaWhiten:
    def __init__(self, N_pic=128):
        self.N_pic = N_pic
        self.whit = SLIP.Image(pe=pe)
        self.whit.set_size((self.N_pic, self.N_pic))
        # https://github.com/bicv/SLIP/blob/master/SLIP/SLIP.py#L611
        self.K_whitening = self.whit.whitening_filt()
    def __call__(self, fullfield):
        white_fullfield = self.whit.FTfilter(fullfield, self.K_whitening) 
        #white_fullfield += 0.5
        #white_fullfield = np.clip(white_fullfield, 0, 1)
        return (white_fullfield, fullfield) #pixel_fullfield.astype('B')    
    
class RetinaTransform:
    def __init__(self, retina_transform_vector):
        self.retina_transform_vector = retina_transform_vector
    def __call__(self, fullfield):
        retina_features = self.retina_transform_vector @ np.ravel(fullfield)
        print("RetinaTransform ok")
        return retina_features

class TransformDico:
    def __init__(self, retina):
        self.retina = retina
        #self.retina_dico = retina_dico
    def __call__(self, fullfield):
        pixel_fullfield, retina_features = self.retina.transform_dico(fullfield)
        return [pixel_fullfield, retina_features]

class InverseTransformDico:
    def __init__(self, retina):
        self.retina = retina
    def __call__(self, list_pixel_fullfield_retina_features):
        rebuild_pixel_fullfield = self.retina.inverse_transform_dico(list_pixel_fullfield_retina_features[1])
        return [list_pixel_fullfield_retina_features[0], rebuild_pixel_fullfield]

class OnlineRetinaTransform:
    def __init__(self, retina):
        self.retina = retina
    def __call__(self, fullfield):
        retina_features = retina.online_vectorization(fullfield)
        return retina_features

class FullfieldRetinaTransform:
    def __init__(self, retina_transform_vector):
        self.retina_transform_vector = retina_transform_vector
    def __call__(self, data):
        white_fullfield = data[0]
        fullfield = data[1]
        retina_features = self.retina_transform_vector @ np.ravel(white_fullfield)
        return (retina_features, fullfield)
    
class CollTransform:
    def __init__(self, colliculus_transform_vector):
        self.colliculus_transform_vector = colliculus_transform_vector
    def __call__(self, acc_map):
        coll_features = self.colliculus_transform_vector @ np.ravel(acc_map)
        return coll_features

class FullfieldCollTransform:
    def __init__(self, colliculus_transform_vector, keep_label = False):
        self.colliculus_transform_vector = colliculus_transform_vector
        self.keep_label = keep_label
    def __call__(self, data):
        if self.keep_label:
            acc_map = data[0]
            label = data[1]
            i_offset = data[2]
            j_offset = data[3]
        else:
            acc_map = data
        coll_features = self.colliculus_transform_vector @ np.ravel(acc_map)
        if self.keep_label:
            return (coll_features, acc_map, label, i_offset, j_offset)
        else:
            return (coll_features, acc_map)
    
class ToFloatTensor:
    def __init__(self):
        pass
    def __call__(self, data):
        return Variable(torch.FloatTensor(data.astype('float')))
    
class FullfieldToFloatTensor:
    def __init__(self, keep_label = False):
        self.keep_label = keep_label
    def __call__(self, data):
        if self.keep_label:
            return (Variable(torch.FloatTensor(data[0].astype('float'))), # logPolar features
                    Variable(torch.FloatTensor(data[1].astype('float'))), # fullfield
                    data[2],                                              # label
                    data[3],                                              # i_offset
                    data[4])                                              # j_offset
        else:
            return (Variable(torch.FloatTensor(data[0].astype('float'))), # logPolar features
                    Variable(torch.FloatTensor(data[1].astype('float')))) # fullfield
    
    
class Normalize:
    def __init__(self, fullfield=False):
        self.fullfield = fullfield
    def __call__(self, data):
        if self.fullfield:
            data_0 = data[0] - data[0].mean() #dim=1, keepdim=True)
            data_0 /= data_0.std() #dim=1, keepdim=True)
            if len(data) > 2:
                return (data_0,) + data[1:] 
            else:
                return (data_0, data[1])
        else:
            data -= data.mean() #dim=1, keepdim=True)
            data /= data.std() #dim=1, keepdim=True)
            return data


class WhereNet(torch.nn.Module):
    def __init__(self, args):
        super(WhereNet, self).__init__()
        self.args = args
        self.bn1 = torch.nn.Linear(args.N_theta*args.N_azimuth*args.N_eccentricity*args.N_phase, args.dim1, bias=args.bias_deconv)
        #https://raw.githubusercontent.com/MorvanZhou/PyTorch-Tutorial/master/tutorial-contents/504_batch_normalization.py
        self.bn1_bn = nn.BatchNorm1d(args.dim1, momentum=1-args.bn1_bn_momentum)
        self.bn2 = torch.nn.Linear(args.dim1, args.dim2, bias=args.bias_deconv)
        self.bn2_bn = nn.BatchNorm1d(args.dim2, momentum=1-args.bn2_bn_momentum)
        self.bn3 = torch.nn.Linear(args.dim2, 5, bias=args.bias_deconv)
        # 5 classes : Happy mouth closed HC, happy mouth open HO, neutral N, angry A, fearful F

    def forward(self, image):
        x = F.relu(self.bn1(image))
        if self.args.bn1_bn_momentum>0: x = self.bn1_bn(x)
        x = F.relu(self.bn2(x))
        if self.args.p_dropout>0: x = F.dropout(x, p=self.args.p_dropout)
        if self.args.bn2_bn_momentum>0: x = self.bn2_bn(x)
        x = self.bn3(x)
        return x

"""
class WhereNet(torch.nn.Module):
    
    def __init__(self, args):
        super(WhereNet, self).__init__()
        self.args = args
        self.bn1 = torch.nn.Linear(args.N_theta*args.N_azimuth*args.N_eccentricity*args.N_phase, args.dim1, bias=args.bias_deconv)
        #https://raw.githubusercontent.com/MorvanZhou/PyTorch-Tutorial/master/tutorial-contents/504_batch_normalization.py
        self.bn1_bn = nn.BatchNorm1d(args.dim1, momentum=1-args.bn1_bn_momentum)
        self.bn2 = torch.nn.Linear(args.dim1, args.dim2, bias=args.bias_deconv)
        self.bn2_bn = nn.BatchNorm1d(args.dim2, momentum=1-args.bn2_bn_momentum)
        self.bn3 = torch.nn.Linear(args.dim2, args.N_azimuth*args.N_eccentricity, bias=args.bias_deconv)
        if self.args.bn1_bn_momentum>0 and self.args.verbose:
            print('BN1 is on')
        if self.args.bn2_bn_momentum>0 and self.args.verbose:
            print('BN2 is on')
        if self.args.p_dropout>0 and self.args.verbose:
            print('Dropout is on')
            
    def forward(self, image):
        x = F.relu(self.bn1(image))
        if self.args.bn1_bn_momentum>0:
            x = self.bn1_bn(x)
        x = F.relu(self.bn2(x))
        if self.args.bn2_bn_momentum>0:
            x = self.bn2_bn(x)
        if self.args.p_dropout>0:
            x = F.dropout(x, p=self.args.p_dropout)
        x = self.bn3(x)
        return x
"""

def where_suffix(args):
    suffix += '_{}_{}'.format(args.N_theta, args.N_azimuth)
    suffix += '_{}_{}'.format(args.N_eccentricity, args.N_phase)
    suffix += '_{}_{}'.format(args.rho, args.N_pic)
    return suffix

class WhereTrainer:
    def __init__(self, args, 
                 model=None,
                 train_loader=None, 
                 test_loader=None, 
                 device='cpu', 
                 generate_data=True,
                 retina=None):
        self.args=args
        self.device=device
        if retina:
            self.retina=retina
        else:
            self.retina = Retina(args)
        kwargs = {'num_workers': 1, 'pin_memory': True} if self.device != 'cpu' else {}
        
        ## DATASET TRANSFORMS     
        self.transform = transforms.Compose([
            WhereSquareCrop(args),
            # gray
            RetinaWhiten(N_pic=args.N_pic),
            TransformDico(self.retina),
            ToFloatTensor(),
        ])
        
        self.target_transform=transforms.Compose([
                               ToFloatTensor()
                           ])

        
        suffix = where_suffix(args)
        
        if not train_loader:
            self.init_data_loader(args, suffix, 
                                  train=True, 
                                  generate_data=generate_data, 
                                  fullfield=False)
        else:
            self.train_loader = train_loader
        
        if not test_loader:
            self.init_data_loader(args, suffix, 
                                  train=False, 
                                  generate_data=generate_data, 
                                  fullfield=True)
        else:
            self.test_loader = test_loader
            
        if not model:
            self.model = WhereNet(args).to(device)
        else:
            self.model = model
            
        self.loss_func = torch.nn.BCEWithLogitsLoss()
        
        if args.do_adam:
            self.optimizer = optim.Adam(self.model.parameters(), lr=args.lr)
        else:
            self.optimizer = optim.SGD(self.model.parameters(), lr=args.lr, momentum=args.momentum)
            
        #if args.do_adam:
        #    # see https://heartbeat.fritz.ai/basics-of-image-classification-with-pytorch-2f8973c51864
        #    self.optimizer = optim.Adam(self.model.parameters(),
        #                                lr=args.lr, 
        #                                betas=(1.-args.momentum, 0.999), 
        #                                eps=1e-8)
        #else:
        #    self.optimizer = optim.SGD(self.model.parameters(),
        #                               lr=args.lr, 
        #                               momentum=args.momentum)
        
    def init_data_loader(self, args, suffix, force_generate = False, train=True):
        if train:
            use = 'train'
        else:
            use = 'test'
        data_loader_path = '/tmp/where_chicago_dataset_{}_{}.pt'.format(suffix, args.minibatch_size) # use retire
        if os.path.isfile(data_loader_path) and not force_generate:
            if self.args.verbose: 
                print('Loading {}ing dataset'.format(use))
            data_loader = torch.load(data_loader_path)
        else:
            if self.args.verbose:
                print('Generating {}ing dataset'.format(use))

            data_loader = ChicagoFacesDataset()

            """
            for i in range(len(dataset))# lire les images # i, (data, acc) in enumerate(data_loader):
                if self.args.verbose:
                    print(i, (i+1) * args.minibatch_size)

                if i == 0:
                    full_data = data
                    full_label = label
                else:
                    full_data = torch.cat((full_data, data), 0)
                    full_label = torch.cat((full_label, label), 0)
            
            
            dataset = TensorDataset(full_data, full_label)
                

            data_loader = DataLoader(dataset,
                                         batch_size=args.minibatch_size,
                                         shuffle=True)
            """

            torch.save(data_loader, data_loader_path)
            if self.args.verbose:
                print('Done!')
        if train:
            self.train_loader = data_loader
        else:
            self.test_loader = data_loader
    
    def train(self, epoch):
        train(self.args, self.model, self.device, self.train_loader, self.loss_func, self.optimizer, epoch)
    
    def test(self):
        return test(self.args, self.model, self.device, self.test_loader, self.loss_func)

def train(args, model, device, train_loader, loss_function, optimizer, epoch):
    # setting up training
    '''if seed is None:
        seed = self.args.seed
    model.train() # set training mode
    for epoch in tqdm(range(1, self.args.epochs + 1), desc='Train Epoch' if self.args.verbose else None):
        loss = self.train_epoch(epoch, seed, rank=0)
        # report classification results
        if self.args.verbose and self.args.log_interval>0:
            if epoch % self.args.log_interval == 0:
                status_str = '\tTrain Epoch: {} \t Loss: {:.6f}'.format(epoch, loss)
                try:
                    #from tqdm import tqdm
                    tqdm.write(status_str)
                except Exception as e:
                    print(e)
                    print(status_str)'''
    
    model.train()
    for batch_idx, (data, target) in enumerate(train_loader):
        data = Variable(torch.FloatTensor(data.float())).to(device)
        ## !!!
        #data = Normalize()(data)
        target = Variable(torch.FloatTensor(target.float())).to(device)
        optimizer.zero_grad()
        output = model(data)
        loss = loss_function(output, target)
        loss.backward()
        optimizer.step()
        if batch_idx % args.log_interval == 0:
            print('Train Epoch: {}/{} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
                epoch, args.epochs, batch_idx * len(data), len(train_loader.dataset),
                100. * batch_idx / len(train_loader), loss.item()))

def test(args, model, device, test_loader, loss_function):
    model.eval()
    test_loss = 0
    with torch.no_grad():
        for batch_idx, (data, data_fullfield, target, target_fullfield, label, i_shift, j_shift) in enumerate(test_loader):
            data = Variable(torch.FloatTensor(data.float())).to(device)
            # !!!
            #data = Normalize()(data)
            target = Variable(torch.FloatTensor(target.float())).to(device)            
            output = model(data)
            test_loss += loss_function(output, target).item() # sum up batch loss
            #if batch_idx % args.log_interval == 0:
            #    print('i = {}, test done on {:.0f}% of the test dataset.'.format(batch_idx, 100. * batch_idx / len(test_loader.dataset)))

    test_loss /= len(test_loader)
    print('\nTest set: Average loss: {:.4f}\n'.format(test_loss))
    return test_loss
            
class Where():
    def __init__(self, args, 
                 save=True, 
                 batch_load=False, 
                 force_training=False, 
                 model=None,
                 train_loader=None, 
                 test_loader=None, 
                 generate_data=True,
                 what_model=None,
                 retina=None,
                 trainer=None,
                 save_model = True):
        
        self.args = args

        # GPU boilerplate
        self.args.no_cuda = self.args.no_cuda or not torch.cuda.is_available()
        # if self.args.verbose: print('cuda?', not self.args.no_cuda)
        self.device = torch.device("cpu" if self.args.no_cuda else "cuda")
        torch.manual_seed(self.args.seed)

        #########################################################
        # loads a WHAT model (or learns it if not already done) #
        #########################################################
        if what_model:
            self.what_model = what_model
        else:
            print(datetime.datetime.now())
            what = What(args) # trains the what_model if needed
            self.what_model = what.model.to(self.device)
            print(datetime.datetime.now())
            
                
        '''from what import WhatNet
        # suffix = f"{self.args.sf_0}_{self.args.B_sf}_{self.args.noise}_{self.args.contrast}"
        suffix = "{}_{}_{}_{}".format(self.args.sf_0, self.args.B_sf, self.args.noise, elf.args.contrast)
        # model_path = f"../data/MNIST_cnn_{suffix}.pt"
        model_path = "../data/MNIST_cnn_{}.pt".format(suffix)
        if not os.path.isfile(model_path):
            train_loader = self.data_loader(suffix, 
                                            train=True,
                                            what = True,
                                            save=save, 
                                            batch_load=batch_load)
            test_loader = self.data_loader(suffix, 
                                            train=False, 
                                            what = True,
                                            save=save, 
                                            batch_load=batch_load)
            print('Training the "what" model ', model_path)
            from what import main
            main(args=self.args, 
                 train_loader=train_loader, 
                 test_loader=test_loader, 
                 path=model_path)
        self.What_model = torch.load(model_path)'''
        
        ######################
        # Accuracy map setup #
        ######################
        
        # TODO generate an accuracy map for different noise / contrast / sf_0 / B_sf
        '''path = "../data/MNIST_accuracy.npy"
        if os.path.isfile(path):
            self.accuracy_map =  np.load(path)
            if args.verbose:
                print('Loading accuracy... min, max=', self.accuracy_map.min(), self.accuracy_map.max())
        else:
            print('No accuracy data found.')'''
            
        
        ######################
        # WHERE model setup  #
        ######################
      
        
        suffix = where_suffix(args)
        model_path = '/tmp/where_model_{}.pt'.format(suffix)
        if model:
            self.model = model
            if trainer:
                self.trainer = trainer
            else:
                self.trainer = WhereTrainer(args, 
                                       model=self.model,
                                       train_loader=train_loader, 
                                       test_loader=test_loader, 
                                       device=self.device,
                                       generate_data=generate_data,
                                       retina=retina)
        elif trainer:
            self.model = trainer.model
            self.trainer = trainer
        elif os.path.exists(model_path) and not force_training:
            self.model  = torch.load(model_path)
            self.trainer = WhereTrainer(args, 
                                       model=self.model,
                                       train_loader=train_loader, 
                                       test_loader=test_loader, 
                                       device=self.device,
                                       generate_data=generate_data,
                                       retina=retina)
        else:                                                       
            self.trainer = WhereTrainer(args, 
                                       train_loader=train_loader, 
                                       test_loader=test_loader, 
                                       device=self.device,
                                       generate_data=generate_data,
                                       retina=retina)
            for epoch in range(1, args.epochs + 1):
                self.trainer.train(epoch)
                self.trainer.test()
            self.model = self.trainer.model
            print(model_path)
            if save_model:
                #torch.save(model.state_dict(), "../data/MNIST_cnn.pt")
                torch.save(self.model, model_path) 
                print('Model saved at', model_path)
                
        self.accuracy_map = self.trainer.accuracy_map
            
        self.display = Display(args)
        if retina:
            self.retina = retina
        else:
            self.retina = self.trainer.retina
        # https://pytorch.org/docs/stable/nn.html#torch.nn.BCEWithLogitsLoss
        self.loss_func = self.trainer.loss_func #torch.nn.BCEWithLogitsLoss()        
        
        if train_loader:
            self.loader_train = train_loader
        else:
            self.loader_train = self.trainer.train_loader
            
        if test_loader:
            self.loader_test = test_loader
        else:
            self.loader_test = self.trainer.test_loader

        if not self.args.no_cuda:
            # print('doing cuda')
            torch.cuda.manual_seed(self.args.seed)
            self.model.cuda()  
    
    def minibatch(self, data=None):
        # TODO: utiliser https://laurentperrinet.github.io/sciblog/posts/2018-09-07-extending-datasets-in-pytorch.html
        '''batch_size = data.shape[0]
        retina_data = np.zeros((batch_size, self.retina.feature_vector_size))
        accuracy_colliculus = np.zeros((batch_size, self.args.N_azimuth * self.args.N_eccentricity))
        data_fullfield = np.zeros((batch_size, self.args.N_pic, self.args.N_pic))
        positions =[]

        for i in range(batch_size):
            #print(i, data[i, 0, :, :].numpy().shape)
            data_fullfield[i, :, :], i_offset, j_offset = self.display.draw(data[i, 0, :, :].numpy())
            positions.append(dict(i_offset=i_offset, j_offset=j_offset))
            # TODO use one shot matrix multiplication
            retina_data[i, :]  =  self.retina.retina(data_fullfield[i, :, :])
            accuracy_colliculus[i,:], _ = self.retina.accuracy_fullfield(self.accuracy_map, i_offset, j_offset)

        retina_data = Variable(torch.FloatTensor(retina_data))
        accuracy_colliculus = Variable(torch.FloatTensor(accuracy_colliculus))
        retina_data, accuracy_colliculus = retina_data.to(self.device), accuracy_colliculus.to(self.device)'''
        retina_data, data_fullfield, accuracy_colliculus, _, label, i_offset, j_offset = next(iter(self.loader_test))
        batch_size = retina_data.shape[0]
        positions = [None] * batch_size
        for idx in range(batch_size):
            positions[idx] = {}
            positions[idx]['i_offset'] = i_offset[idx]
            positions[idx]['j_offset'] = j_offset[idx]
        return positions, data_fullfield, retina_data, accuracy_colliculus

    def extract(self, data_fullfield, i_offset, j_offset):
        mid = self.args.N_pic//2
        rad = self.args.w//2

        im = data_fullfield[(mid+i_offset-rad):(mid+i_offset+rad),
                            (mid+j_offset-rad):(mid+j_offset+rad)]

        im = np.clip(im, 0.5, 1)
        im = (im-.5)*2
        return im

    def classify_what(self, im):
        im = (im-self.args.mean)/self.args.std
        if im.ndim ==2:
            im = Variable(torch.FloatTensor(im[None, None, ::]))
        else:
            im = Variable(torch.FloatTensor(im[:, None, ::]))
        with torch.no_grad():
            output = self.what_model(im)

        return np.exp(output) #nn.softmax(output)

    def pred_accuracy(self, retina_data):
        # Predict classes using images from the train set
        retina_data = Variable(torch.FloatTensor(retina_data))
        prediction = self.model(retina_data)
        # transform in a probability in collicular coordinates
        pred_accuracy_colliculus = F.sigmoid(prediction).detach().numpy()
        return pred_accuracy_colliculus

    def index_prediction(self, pred_accuracy_colliculus, do_shortcut=True):
        if do_shortcut:
            test = pred_accuracy_colliculus.reshape((self.args.N_azimuth, self.args.N_eccentricity))
            indices_ij = np.where(test == max(test.flatten()))
            azimuth = indices_ij[0][0]
            eccentricity = indices_ij[1][0]
            im_colliculus = self.retina.colliculus_transform[azimuth, eccentricity, :].reshape((self.args.N_pic, self.args.N_pic))
        else:
            im_colliculus = self.retina.accuracy_invert(pred_accuracy_colliculus)

        # see https://laurentperrinet.github.io/sciblog/posts/2016-11-17-finding-extremal-values-in-a-nd-array.html
        i, j = np.unravel_index(np.argmax(im_colliculus.ravel()), im_colliculus.shape)
        i_pred = i - self.args.N_pic//2
        j_pred = j - self.args.N_pic//2
        return i_pred, j_pred
    
    def what_class(self, data_fullfield, pred_accuracy_colliculus, do_control=False):
        batch_size = pred_accuracy_colliculus.shape[0]
        # extract foveal images
        im = np.zeros((batch_size, self.args.w, self.args.w))
        for idx in range(batch_size):
            if do_control:
                i_pred, j_pred = 0, 0
            else:
                i_pred, j_pred = self.index_prediction(pred_accuracy_colliculus[idx, :])
            # avoid going beyond the border (for extraction)
            border = self.args.N_pic//2 - self.args.w//2
            i_pred, j_pred = minmax(i_pred, border), minmax(j_pred, border)
            im[idx, :, :] = self.extract(data_fullfield[idx, :, :], i_pred, j_pred)
        # classify those images
        proba = self.classify_what(im).numpy()
        return proba.argmax(axis=1) # get the index of the max log-probability

    def test_what(self, data_fullfield, pred_accuracy_colliculus, digit_labels, do_control=False):
        pred = self.what_class(data_fullfield, pred_accuracy_colliculus, do_control=do_control)
        #print(im.shape, batch_size, proba.shape, pred.shape, label.shape)
        return (pred==digit_labels.numpy())*1.



    def train(self, path=None, seed=None):
        if path is not None:
            # using a data_cache
            if os.path.isfile(path):
                #self.model.load_state_dict(torch.load(path))
                self.model = torch.load(path)
                print('Loading file', path)
            else:
                #print('Training model...')
                #self.train(path=None, seed=seed)
                for epoch in range(1, args.epochs + 1):
                    self.trainer.train(epoch)
                    self.trainer.test()
                torch.save(self.model, path)
                #torch.save(self.model.state_dict(), path) #save the neural network state
                print('Model saved at', path)
        else:
            # from tqdm import tqdm # commenter car ne sert pas et hydra ne veut pas sinon
            # setting up training
            if seed is None:
                seed = self.args.seed
                
            for epoch in range(1, args.epochs + 1):
                self.trainer.train(epoch)
                self.trainer.test()

            '''self.model.train() # set training mode
            for epoch in (range(1, self.args.epochs + 1), desc='Train Epoch' if self.args.verbose else None):
                loss = self.train_epoch(epoch, seed, rank=0)
                # report classification results
                if self.args.verbose and self.args.log_interval>0:
                    if epoch % self.args.log_interval == 0:
                        status_str = '\tTrain Epoch: {} \t Loss: {:.6f}'.format(epoch, loss)
                        try:
                            #from tqdm import tqdm
                            tqdm.write(status_str)
                        except Exception as e:
                            print(e)
                            print(status_str)
            self.model.eval()'''

    '''def train_epoch(self, epoch, seed, rank=0):
        torch.manual_seed(seed + epoch + rank*self.args.epochs)
        for retina_data, accuracy_colliculus in self.loader_train:
            # Clear all accumulated gradients
            self.optimizer.zero_grad()

            # Predict classes using images from the train set
            prediction = self.model(retina_data)
            # Compute the loss based on the predictions and actual labels
            loss = self.loss_func(prediction, accuracy_colliculus)
            # TODO try with the reverse divergence
            # loss = self.loss_func(accuracy_colliculus, prediction)
            # Backpropagate the loss
            loss.backward()
            # Adjust parameters according to the computed gradients
            self.optimizer.step()

        return loss.item()'''

    def test(self, dataloader=None):
        if dataloader is None:
            dataloader = self.loader_test
        self.model.eval()
        accuracy = []
        for retina_data, data_fullfield, accuracy_colliculus, accuracy_fullfield, digit_labels, i_shift, j_shift in dataloader:
            #retina_data = Variable(torch.FloatTensor(retina_data.float())).to(self.device)
            pred_accuracy_colliculus = self.pred_accuracy(retina_data)
            # use that predicted map to extract the foveal patch and classify the image
            correct = self.test_what(data_fullfield.numpy(), pred_accuracy_colliculus, digit_labels.squeeze())
            accuracy.append(correct.mean())
        return np.mean(accuracy)

    def multi_test(self, nb_saccades, dataloader=None):
        # multi-saccades
        if dataloader is None:
            dataloader = self.loader_test
        self.model.eval()
        #accuracy = []
        #for retina_data, data_fullfield, accuracy_colliculus, accuracy_fullfield, digit_labels, i_shift, j_shift in dataloader:
        (retina_data, data_fullfield), (accuracy_colliculus, accuracy_fullfield, digit_labels, i_shift, j_shift) = next(iter(dataloader))
        #retina_data = Variable(torch.FloatTensor(retina_data.float())).to(self.device)
        pred_accuracy_colliculus = self.pred_accuracy(retina_data)
        
        # use that predicted map to extract the foveal patch and classify the image
        if nb_saccades > 1:
            for idx in range(self.args.minibatch_size):
                i_ref, j_ref = 0, 0
                pred_accuracy_trans = pred_accuracy_colliculus[idx, :]
                fullfield_ref = data_fullfield[idx, :, :]
                #coll_ref = accuracy_fullfield[idx, :, :]
                for num_saccade in range(nb_saccades - 1):
                    i_pred, j_pred = self.index_prediction(pred_accuracy_trans)
                    i_ref += i_pred
                    j_ref += j_pred
                    fullfield_shift = WhereShift(self.args, i_offset=-i_ref, j_offset=-j_ref, baseline=0.5)((fullfield_ref, 0))
                    retina_shift = self.retina.retina(fullfield_shift)
                    #coll_shift = WhereShift(self.args, i_offset=-i_ref, j_offset=-j_ref, baseline=0.1)((coll_ref, 0))
                    pred_accuracy_trans = self.pred_accuracy(retina_shift)
                    if idx == 0:
                        plt.imshow(fullfield_shift)
                        plt.show()
                        print(num_saccade, i_ref, j_ref)
                data_fullfield[idx, :, :] = Variable(torch.FloatTensor(fullfield_shift))
                #accuracy_fullfield[idx, :, :] = coll_shift
                pred_accuracy_colliculus[idx, :] = pred_accuracy_trans

        correct = self.test_what(data_fullfield.numpy(), pred_accuracy_colliculus, digit_labels.squeeze())
        print(correct)
        return np.mean(correct)

    def show(self, gamma=.5, noise_level=.4, transpose=True, only_wrong=False):
        for idx, (data, target) in enumerate(self.display.loader_test):
            #data, target = next(iter(self.dataset.test_loader))
            data, target = data.to(self.device), target.to(self.device)
            output = self.model(data)
            pred = output.data.max(1, keepdim=True)[1] # get the index of the max log-probability
            if only_wrong and not pred == target:
                #print(target, self.dataset.dataset.imgs[self.dataset.test_loader.dataset.indices[idx]])
                print('target:' + ' '.join('%5s' % self.dataset.dataset.classes[j] for j in target))
                print('pred  :' + ' '.join('%5s' % self.dataset.dataset.classes[j] for j in pred))
                #print(target, pred)

                from torchvision.utils import make_grid
                npimg = make_grid(data, normalize=True).numpy()
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots(figsize=((13, 5)))
                import numpy as np
                if transpose:
                    ax.imshow(np.transpose(npimg, (1, 2, 0)))
                else:
                    ax.imshow(npimg)
                plt.setp(ax, xticks=[], yticks=[])

                return fig, ax
            else:
                return None, None


    def main(self, path=None, seed=None):
        self.train(path=path, seed=seed)
        Accuracy = self.test()
        return Accuracy

if __name__ == '__main__':

    from main import init, MetaML
    import os
    filename = 'figures/accuracy.pdf'
    if not os.path.exists(filename) :
        args = init(verbose=0, log_interval=0, epochs=20)
        from gaze import MetaML
        mml = MetaML(args)
        Accuracy = mml.protocol(args, 42)
        print('Accuracy', Accuracy[:-1].mean(), '+/-', Accuracy[:-1].std())
        import numpy as np
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=((8, 5)))
        n, bins, patches = ax.hist(Accuracy[:-1]*100, bins=np.linspace(0, 100, 100), alpha=.4)
        ax.vlines(np.median(Accuracy[:-1])*100, 0, n.max(), 'g', linestyles='dashed', label='median')
        ax.vlines(25, 0, n.max(), 'r', linestyles='dashed', label='chance level')
        ax.vlines(100, 0, n.max(), 'k', label='max')
        ax.set_xlabel('Accuracy (%)')
        ax.set_ylabel('Smarts')
        ax.legend(loc='best')
        plt.show()
        plt.savefig(filename)
        plt.savefig(filename.replace('.pdf', '.png'))