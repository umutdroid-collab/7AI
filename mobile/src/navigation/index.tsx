import React from "react";
import { ActivityIndicator, View } from "react-native";
import { NavigationContainer, DarkTheme } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { useAuth } from "../context/AuthContext";
import { colors } from "../theme";
import HeaderProfileButton from "../components/HeaderProfileButton";

import LoginScreen from "../screens/auth/LoginScreen";
import StockListScreen from "../screens/stock/StockListScreen";
import StockDetailScreen from "../screens/stock/StockDetailScreen";
import TransferStockScreen from "../screens/stock/TransferStockScreen";
import AddStockScreen from "../screens/stock/AddStockScreen";
import AddHospitalScreen from "../screens/stock/AddHospitalScreen";
import HospitalListScreen from "../screens/stock/HospitalListScreen";
import AddProductScreen from "../screens/stock/AddProductScreen";
import ProductListScreen from "../screens/stock/ProductListScreen";
import InvoiceListScreen from "../screens/invoices/InvoiceListScreen";
import InvoiceDetailScreen from "../screens/invoices/InvoiceDetailScreen";
import NotificationsScreen from "../screens/invoices/NotificationsScreen";
import AssistantChatScreen from "../screens/assistant/AssistantChatScreen";
import CheckInScreen from "../screens/checkins/CheckInScreen";
import ProfileScreen from "../screens/profile/ProfileScreen";
import BulkUploadScreen from "../screens/profile/BulkUploadScreen";
import PersonelTakipScreen from "../screens/targets/PersonelTakipScreen";
import AddSalesTargetScreen from "../screens/targets/AddSalesTargetScreen";

const StockStackNav = createNativeStackNavigator();
const InvoiceStackNav = createNativeStackNavigator();
const AssistantStackNav = createNativeStackNavigator();
const CheckInStackNav = createNativeStackNavigator();
const TargetsStackNav = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

const screenOptions = {
  headerStyle: { backgroundColor: colors.surface },
  headerTintColor: colors.text,
  contentStyle: { backgroundColor: colors.background },
};

function StockStack() {
  return (
    <StockStackNav.Navigator screenOptions={screenOptions}>
      <StockStackNav.Screen
        name="StockList"
        component={StockListScreen}
        options={({ navigation }) => ({ title: "Stok Takip", headerRight: () => <HeaderProfileButton navigation={navigation} /> })}
      />
      <StockStackNav.Screen name="StockDetail" component={StockDetailScreen} options={{ title: "Ürün Detayı" }} />
      <StockStackNav.Screen name="TransferStock" component={TransferStockScreen} options={{ title: "Taşı" }} />
      <StockStackNav.Screen name="AddStock" component={AddStockScreen} options={{ title: "Yeni Stok Kaydı" }} />
      <StockStackNav.Screen name="AddHospital" component={AddHospitalScreen} options={{ title: "Yeni Hastane" }} />
      <StockStackNav.Screen name="HospitalList" component={HospitalListScreen} options={{ title: "Hastaneler" }} />
      <StockStackNav.Screen name="AddProduct" component={AddProductScreen} options={{ title: "Yeni Ürün" }} />
      <StockStackNav.Screen name="ProductList" component={ProductListScreen} options={{ title: "Ürünler" }} />
      <StockStackNav.Screen name="Profile" component={ProfileScreen} options={{ title: "Profil" }} />
      <StockStackNav.Screen name="BulkUpload" component={BulkUploadScreen} options={{ title: "Toplu Ekleme" }} />
    </StockStackNav.Navigator>
  );
}

function InvoiceStack() {
  return (
    <InvoiceStackNav.Navigator screenOptions={screenOptions}>
      <InvoiceStackNav.Screen
        name="InvoiceList"
        component={InvoiceListScreen}
        options={({ navigation }) => ({ title: "Fatura Takip", headerRight: () => <HeaderProfileButton navigation={navigation} /> })}
      />
      <InvoiceStackNav.Screen name="InvoiceDetail" component={InvoiceDetailScreen} options={{ title: "Fatura Detayı" }} />
      <InvoiceStackNav.Screen name="Notifications" component={NotificationsScreen} options={{ title: "Bildirimler" }} />
      <InvoiceStackNav.Screen name="Profile" component={ProfileScreen} options={{ title: "Profil" }} />
      <InvoiceStackNav.Screen name="BulkUpload" component={BulkUploadScreen} options={{ title: "Toplu Ekleme" }} />
    </InvoiceStackNav.Navigator>
  );
}

function AssistantStack() {
  return (
    <AssistantStackNav.Navigator screenOptions={screenOptions}>
      <AssistantStackNav.Screen
        name="AssistantChat"
        component={AssistantChatScreen}
        options={({ navigation }) => ({ title: "Klinik Asistan", headerRight: () => <HeaderProfileButton navigation={navigation} /> })}
      />
      <AssistantStackNav.Screen name="Profile" component={ProfileScreen} options={{ title: "Profil" }} />
      <AssistantStackNav.Screen name="BulkUpload" component={BulkUploadScreen} options={{ title: "Toplu Ekleme" }} />
    </AssistantStackNav.Navigator>
  );
}

function CheckInStack() {
  return (
    <CheckInStackNav.Navigator screenOptions={screenOptions}>
      <CheckInStackNav.Screen
        name="CheckIn"
        component={CheckInScreen}
        options={({ navigation }) => ({ title: "Çalışan Takip", headerRight: () => <HeaderProfileButton navigation={navigation} /> })}
      />
      <CheckInStackNav.Screen name="Profile" component={ProfileScreen} options={{ title: "Profil" }} />
      <CheckInStackNav.Screen name="BulkUpload" component={BulkUploadScreen} options={{ title: "Toplu Ekleme" }} />
    </CheckInStackNav.Navigator>
  );
}

function TargetsStack() {
  return (
    <TargetsStackNav.Navigator screenOptions={screenOptions}>
      <TargetsStackNav.Screen
        name="PersonelTakip"
        component={PersonelTakipScreen}
        options={({ navigation }) => ({ title: "Personel Takip", headerRight: () => <HeaderProfileButton navigation={navigation} /> })}
      />
      <TargetsStackNav.Screen name="AddSalesTarget" component={AddSalesTargetScreen} options={{ title: "Yeni Hedef" }} />
      <TargetsStackNav.Screen name="Profile" component={ProfileScreen} options={{ title: "Profil" }} />
      <TargetsStackNav.Screen name="BulkUpload" component={BulkUploadScreen} options={{ title: "Toplu Ekleme" }} />
    </TargetsStackNav.Navigator>
  );
}

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textMuted,
      }}
    >
      <Tab.Screen name="Stok" component={StockStack} options={{ tabBarLabel: "Stok Takip" }} />
      <Tab.Screen name="Fatura" component={InvoiceStack} options={{ tabBarLabel: "Fatura Takip" }} />
      <Tab.Screen name="Asistan" component={AssistantStack} options={{ tabBarLabel: "Klinik Asistan" }} />
      <Tab.Screen name="Takip" component={CheckInStack} options={{ tabBarLabel: "Çalışan Takip" }} />
      <Tab.Screen name="Personel" component={TargetsStack} options={{ tabBarLabel: "Personel" }} />
    </Tab.Navigator>
  );
}

const navTheme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: colors.background,
    card: colors.surface,
    border: colors.border,
    primary: colors.primary,
    text: colors.text,
  },
};

export default function RootNavigator() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.background, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  return <NavigationContainer theme={navTheme}>{user ? <MainTabs /> : <LoginScreen />}</NavigationContainer>;
}
